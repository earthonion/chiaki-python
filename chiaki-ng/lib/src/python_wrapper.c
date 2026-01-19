/*
 * Python-friendly wrapper for Chiaki library
 * Exposes simplified functions for: discovery, controller, screenshots, app detection
 *
 * Copyright (C) 2024 chiaki-python contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#include <chiaki/session.h>
#include <chiaki/controller.h>
#include <chiaki/discovery.h>
#include <chiaki/thread.h>
#include <chiaki/log.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>   // for fprintf debug
#include <unistd.h>  // for usleep

// Maximum frame buffer size (4MB should be enough for 1080p)
#define MAX_FRAME_SIZE (4 * 1024 * 1024)

// Simple session handle that Python can use
typedef struct {
    ChiakiSession session;
    ChiakiLog log;
    ChiakiThread session_thread;
    bool connected;
    bool quit;
    uint8_t *latest_frame;
    size_t latest_frame_size;
    uint64_t frame_seq;  // Increments with each new frame
    // Store SPS/PPS for building complete I-frames
    uint8_t *sps_pps;
    size_t sps_pps_size;
    // Store a complete I-frame (SPS + PPS + IDR)
    uint8_t *iframe;
    size_t iframe_size;
    bool have_iframe;
    ChiakiMutex frame_mutex;
} PythonSession;

// Debug: track frame count and sizes
static int frame_count = 0;
static size_t max_frame_size = 0;

// Helper: Find NAL unit type from buffer (looks for 00 00 00 01 or 00 00 01 start code)
static int get_first_nal_type(uint8_t *buf, size_t buf_size)
{
    if (buf_size < 5)
        return -1;
    // Check for 4-byte start code: 00 00 00 01
    if (buf[0] == 0 && buf[1] == 0 && buf[2] == 0 && buf[3] == 1)
        return buf[4] & 0x1f;
    // Check for 3-byte start code: 00 00 01
    if (buf[0] == 0 && buf[1] == 0 && buf[2] == 1)
        return buf[3] & 0x1f;
    return -1;
}

// Global callback for video frames
// Chiaki sends: 1) header (SPS/PPS, small) 2) frame data (I or P frames, larger)
static bool video_frame_cb(uint8_t *buf, size_t buf_size, int32_t frames_lost, bool frame_recovered, void *user)
{
    PythonSession *sess = (PythonSession *)user;
    if (!sess || buf_size == 0)
        return true;

    frame_count++;
    if (buf_size > max_frame_size)
        max_frame_size = buf_size;

    int nal_type = get_first_nal_type(buf, buf_size);

    // Log first 20 frames and every 100th frame, with NAL type
    if (frame_count <= 20 || frame_count % 100 == 0) {
        fprintf(stderr, "[PY_WRAPPER] Frame %d: size=%zu NAL=%d", frame_count, buf_size, nal_type);
        if (buf_size >= 8) {
            fprintf(stderr, " [%02x %02x %02x %02x %02x %02x %02x %02x]",
                    buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[6], buf[7]);
        }
        fprintf(stderr, "\n");
        fflush(stderr);
    }

    chiaki_mutex_lock(&sess->frame_mutex);

    // Store the latest frame (always)
    if (sess->latest_frame)
        free(sess->latest_frame);
    sess->latest_frame = malloc(buf_size);
    if (sess->latest_frame) {
        memcpy(sess->latest_frame, buf, buf_size);
        sess->latest_frame_size = buf_size;
        sess->frame_seq++;  // Increment sequence for new frame detection
    }

    // Detect SPS (NAL type 7) or PPS (NAL type 8) - these are the codec headers
    // Also accept if buf contains both SPS and PPS (profile header from chiaki)
    bool is_header = (nal_type == 7 || nal_type == 8);

    // Store headers (SPS/PPS) when we see them
    if (is_header || (buf_size < 500 && nal_type == 7)) {
        fprintf(stderr, "[PY_WRAPPER] Got header! NAL=%d size=%zu\n", nal_type, buf_size);
        fflush(stderr);
        // Replace header buffer with new header
        if (sess->sps_pps)
            free(sess->sps_pps);
        sess->sps_pps = malloc(buf_size);
        if (sess->sps_pps) {
            memcpy(sess->sps_pps, buf, buf_size);
            sess->sps_pps_size = buf_size;
        }
    }

    // Detect I-frames: NAL type 5 (IDR) or large frames > 50KB (non-IDR I-slices)
    bool is_idr = (nal_type == 5);
    bool is_large_iframe = (buf_size > 50000);
    bool is_iframe = is_idr || is_large_iframe;

    // Store I-frames with header for screenshots
    if (is_iframe) {
        fprintf(stderr, "[PY_WRAPPER] I-frame detected! NAL=%d size=%zu sps_pps=%zu\n",
                nal_type, buf_size, sess->sps_pps_size);
        fflush(stderr);
    }
    if (is_iframe && sess->sps_pps && sess->sps_pps_size > 0) {
        size_t total_size = sess->sps_pps_size + buf_size;
        if (total_size <= MAX_FRAME_SIZE) {
            if (sess->iframe)
                free(sess->iframe);
            sess->iframe = malloc(total_size);
            if (sess->iframe) {
                // Prepend header (SPS/PPS) to frame data
                memcpy(sess->iframe, sess->sps_pps, sess->sps_pps_size);
                memcpy(sess->iframe + sess->sps_pps_size, buf, buf_size);
                sess->iframe_size = total_size;
                sess->have_iframe = true;
                fprintf(stderr, "[PY_WRAPPER] Stored complete I-frame: %zu bytes\n", total_size);
                fflush(stderr);
            }
        }
    }

    chiaki_mutex_unlock(&sess->frame_mutex);
    return true;
}

// Event callback
static void event_cb(ChiakiEvent *event, void *user)
{
    PythonSession *sess = (PythonSession *)user;
    if (!sess)
        return;

    switch(event->type) {
        case CHIAKI_EVENT_CONNECTED:
            sess->connected = true;
            break;
        case CHIAKI_EVENT_QUIT:
            sess->quit = true;
            break;
        default:
            break;
    }
}

// Simplified session creation that loads from Chiaki config
CHIAKI_EXPORT PythonSession *chiaki_python_session_create(
    const char *host,
    const char *regist_key_hex,
    const char *rp_key_hex,
    const uint8_t *psn_account_id,  // 8 bytes
    bool is_ps5,
    int resolution_preset,  // 1=360p, 2=540p, 3=720p, 4=1080p
    int fps_preset)         // 30 or 60
{
    PythonSession *sess = calloc(1, sizeof(PythonSession));
    if (!sess)
        return NULL;

    // Initialize mutex
    chiaki_mutex_init(&sess->frame_mutex, false);

    // Set up logging
    chiaki_log_init(&sess->log, CHIAKI_LOG_ALL, NULL, NULL);

    // Set up video profile
    ChiakiConnectVideoProfile video_profile;
    chiaki_connect_video_profile_preset(&video_profile, resolution_preset, fps_preset);

    // Set up connect info
    ChiakiConnectInfo connect_info = {0};
    connect_info.ps5 = is_ps5;
    connect_info.host = host;

    // Regist key is stored as ASCII string (e.g., "d77687f8"), not hex-decoded
    // It gets sent directly in the HTTP header
    memset(connect_info.regist_key, 0, sizeof(connect_info.regist_key));
    size_t regist_len = strlen(regist_key_hex);
    if (regist_len > sizeof(connect_info.regist_key))
        regist_len = sizeof(connect_info.regist_key);
    memcpy(connect_info.regist_key, regist_key_hex, regist_len);

    // RP key (morning field) IS hex-decoded (16 bytes from 32 hex chars)
    size_t rp_len = strlen(rp_key_hex);
    for (size_t i = 0; i < rp_len && i < 32; i += 2) {
        char hex[3] = {rp_key_hex[i], rp_key_hex[i+1], 0};
        connect_info.morning[i/2] = (uint8_t)strtol(hex, NULL, 16);
    }

    // PSN account ID
    if (psn_account_id)
        memcpy(connect_info.psn_account_id, psn_account_id, 8);

    connect_info.video_profile = video_profile;
    connect_info.video_profile_auto_downgrade = true;
    connect_info.enable_keyboard = false;
    connect_info.enable_dualsense = false;
    connect_info.audio_video_disabled = 0;
    connect_info.auto_regist = false;
    connect_info.holepunch_session = NULL;
    connect_info.rudp_sock = NULL;
    connect_info.packet_loss_max = 0.0;
    connect_info.enable_idr_on_fec_failure = true;

    // Initialize session
    ChiakiErrorCode err = chiaki_session_init(&sess->session, &connect_info, &sess->log);
    if (err != CHIAKI_ERR_SUCCESS) {
        free(sess);
        return NULL;
    }

    // Set up callbacks
    chiaki_session_set_event_cb(&sess->session, event_cb, sess);
    chiaki_session_set_video_sample_cb(&sess->session, video_frame_cb, sess);

    fprintf(stderr, "[PY_WRAPPER] Session created, video callback set: %p, user: %p\n",
            (void*)sess->session.video_sample_cb, (void*)sess->session.video_sample_cb_user);
    fflush(stderr);

    return sess;
}

// Start the session
CHIAKI_EXPORT bool chiaki_python_session_start(PythonSession *sess)
{
    if (!sess)
        return false;

    ChiakiErrorCode err = chiaki_session_start(&sess->session);
    return err == CHIAKI_ERR_SUCCESS;
}

// Wait for connection
CHIAKI_EXPORT bool chiaki_python_session_wait_connected(PythonSession *sess, int timeout_ms)
{
    if (!sess)
        return false;

    int elapsed = 0;
    while (!sess->connected && !sess->quit && elapsed < timeout_ms) {
        usleep(100000);  // 100ms
        elapsed += 100;
    }

    return sess->connected;
}

// Check if connected
CHIAKI_EXPORT bool chiaki_python_session_is_connected(PythonSession *sess)
{
    return sess && sess->connected;
}

// Send controller state
CHIAKI_EXPORT bool chiaki_python_session_set_controller(
    PythonSession *sess,
    uint32_t buttons,        // Bitmask of buttons
    int16_t left_x,          // -32768 to 32767
    int16_t left_y,
    int16_t right_x,
    int16_t right_y,
    uint8_t l2_state,        // 0-255
    uint8_t r2_state)
{
    if (!sess || !sess->connected)
        return false;

    ChiakiControllerState state;
    chiaki_controller_state_set_idle(&state);

    state.buttons = buttons;
    state.left_x = left_x;
    state.left_y = left_y;
    state.right_x = right_x;
    state.right_y = right_y;
    state.l2_state = l2_state;
    state.r2_state = r2_state;

    ChiakiErrorCode err = chiaki_session_set_controller_state(&sess->session, &state);
    return err == CHIAKI_ERR_SUCCESS;
}

// Get latest video frame (returns size, writes to buffer)
// Also returns the frame sequence number via out parameter
CHIAKI_EXPORT size_t chiaki_python_session_get_frame_ex(
    PythonSession *sess,
    uint8_t *buffer,
    size_t buffer_size,
    uint64_t *seq_out)
{
    if (!sess || !buffer)
        return 0;

    chiaki_mutex_lock(&sess->frame_mutex);

    size_t size = 0;
    if (sess->latest_frame && sess->latest_frame_size <= buffer_size) {
        memcpy(buffer, sess->latest_frame, sess->latest_frame_size);
        size = sess->latest_frame_size;
        if (seq_out)
            *seq_out = sess->frame_seq;
    }

    chiaki_mutex_unlock(&sess->frame_mutex);

    return size;
}

// Simple version without sequence number
CHIAKI_EXPORT size_t chiaki_python_session_get_frame(
    PythonSession *sess,
    uint8_t *buffer,
    size_t buffer_size)
{
    return chiaki_python_session_get_frame_ex(sess, buffer, buffer_size, NULL);
}

// Get current frame sequence number (for detecting new frames)
CHIAKI_EXPORT uint64_t chiaki_python_session_get_frame_seq(PythonSession *sess)
{
    if (!sess)
        return 0;
    return sess->frame_seq;
}

// Get a complete I-frame (keyframe) for screenshots
// Returns a self-contained H.264 frame (SPS + PPS + IDR) that can be decoded standalone
CHIAKI_EXPORT size_t chiaki_python_session_get_iframe(
    PythonSession *sess,
    uint8_t *buffer,
    size_t buffer_size)
{
    if (!sess || !buffer)
        return 0;

    chiaki_mutex_lock(&sess->frame_mutex);

    size_t size = 0;
    if (sess->have_iframe && sess->iframe && sess->iframe_size <= buffer_size) {
        memcpy(buffer, sess->iframe, sess->iframe_size);
        size = sess->iframe_size;
    }

    chiaki_mutex_unlock(&sess->frame_mutex);

    return size;
}

// Check if an I-frame is available
CHIAKI_EXPORT bool chiaki_python_session_has_iframe(PythonSession *sess)
{
    if (!sess)
        return false;
    return sess->have_iframe;
}

// Clear the current I-frame to wait for a fresh one
CHIAKI_EXPORT void chiaki_python_session_clear_iframe(PythonSession *sess)
{
    if (!sess)
        return;
    chiaki_mutex_lock(&sess->frame_mutex);
    sess->have_iframe = false;
    chiaki_mutex_unlock(&sess->frame_mutex);
}

// Request a fresh IDR frame from the PS4
#include <chiaki/streamconnection.h>

CHIAKI_EXPORT bool chiaki_python_session_request_idr(PythonSession *sess)
{
    if (!sess || !sess->connected)
        return false;

    // Clear current iframe and request new one
    chiaki_mutex_lock(&sess->frame_mutex);
    sess->have_iframe = false;
    chiaki_mutex_unlock(&sess->frame_mutex);

    ChiakiErrorCode err = stream_connection_send_idr_request(&sess->session.stream_connection);
    if (err == CHIAKI_ERR_SUCCESS) {
        fprintf(stderr, "[PY_WRAPPER] Requested IDR frame\n");
        fflush(stderr);
    }
    return err == CHIAKI_ERR_SUCCESS;
}

// Stop session
CHIAKI_EXPORT void chiaki_python_session_stop(PythonSession *sess)
{
    if (!sess)
        return;

    chiaki_session_stop(&sess->session);
    chiaki_session_join(&sess->session);
}

// Destroy session
CHIAKI_EXPORT void chiaki_python_session_destroy(PythonSession *sess)
{
    if (!sess)
        return;

    chiaki_session_fini(&sess->session);

    chiaki_mutex_lock(&sess->frame_mutex);
    if (sess->latest_frame)
        free(sess->latest_frame);
    if (sess->sps_pps)
        free(sess->sps_pps);
    if (sess->iframe)
        free(sess->iframe);
    chiaki_mutex_unlock(&sess->frame_mutex);

    chiaki_mutex_fini(&sess->frame_mutex);
    free(sess);
}

// Simple discovery function
CHIAKI_EXPORT bool chiaki_python_discover(
    const char *host,
    char *host_name_out,      // Buffer for hostname (size 256)
    char *running_app_out,    // Buffer for app name (size 256)
    bool *is_ready_out)       // Is console ready
{
    // TODO: Implement using chiaki_discovery
    // For now, return false - we can use chiaki-cli for discovery
    return false;
}
