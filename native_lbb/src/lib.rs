use std::collections::HashMap;
use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::process::{Child, Command};
use std::sync::{Mutex, OnceLock};
use std::thread;
use std::time::{Duration, Instant};

const CSS_SNIPPET: &str = "\
\t<style>\n\tbody{\n\t\tfont-family: Arial, sans-serif;\n\t\tline-height: 1.6;\n\t\tcolor: #333;\n\t\tbackground-color: #f4f4f4;\n\t\tpadding: 20px;\n\t}\n\t\n\tul {\n\t\tlist-style-type: none;\n\t\tpadding-left:0;\n\t}\n\t\n\tul li {\n\t\tmargin: 5px 0;\n\t\tposition: relative;\n\t\tpadding: 5px;\n\t\tborder: 2px solid #ddd;\n\t\tbackground-color:#fffff;\n\t}\n\t\n\tul li ul {\n\t\tmargin-left: 20px;\n\t\tpadding-left: 20px;\n\t\tborder-left:1.2px dashed #888;\n\t}\n\t\n\tul li:before{\n\t\tcontent: '➡️';\n\t\tposition: absolute;\n\t\tleft:-15px;\n\t\tcolor: #888;\n\t}\n\t\n\t.attributes {\n\t\tcolor: #0000FF;\n\t\tfont-style: italic ;\n\t}\n\t\n\t.text {\n\t\tcolor: #008000;\n\t}\n\t</style>\n\t";

static LAST_ERROR: OnceLock<Mutex<String>> = OnceLock::new();

struct RecordingHandle {
    child: Child,
}

static RECORDING_PROCESSES: OnceLock<Mutex<HashMap<String, RecordingHandle>>> = OnceLock::new();

fn recording_registry() -> &'static Mutex<HashMap<String, RecordingHandle>> {
    RECORDING_PROCESSES.get_or_init(|| Mutex::new(HashMap::new()))
}

fn set_last_error(message: impl Into<String>) {
    let locker = LAST_ERROR.get_or_init(|| Mutex::new(String::new()));
    if let Ok(mut guard) = locker.lock() {
        *guard = message.into();
    }
}

fn clear_last_error() {
    set_last_error(String::new());
}

#[no_mangle]
pub extern "C" fn lb_last_error() -> *mut c_char {
    let locker = LAST_ERROR.get_or_init(|| Mutex::new(String::new()));
    match locker.lock() {
        Ok(guard) => match CString::new(guard.as_str()) {
            Ok(c_string) => c_string.into_raw(),
            Err(_) => std::ptr::null_mut(),
        },
        Err(_) => std::ptr::null_mut(),
    }
}

#[no_mangle]
pub extern "C" fn lb_free_string(ptr: *mut c_char) {
    if ptr.is_null() {
        return;
    }
    unsafe {
        let _ = CString::from_raw(ptr);
    }
}

#[derive(Default)]
struct FrameState {
    has_children: bool,
}

fn escape_html(input: &str) -> String {
    let mut escaped = String::with_capacity(input.len());
    for ch in input.chars() {
        match ch {
            '&' => escaped.push_str("&amp;"),
            '<' => escaped.push_str("&lt;"),
            '>' => escaped.push_str("&gt;"),
            '"' => escaped.push_str("&quot;"),
            '\'' => escaped.push_str("&#39;"),
            _ => escaped.push(ch),
        }
    }
    escaped
}

fn render_device_ui_html(xml: &str) -> Result<String, String> {
    let mut output = String::with_capacity(xml.len().saturating_mul(2));
    output.push_str(CSS_SNIPPET);
    output.push_str("<ul>");

    let bytes = xml.as_bytes();
    let mut index: usize = 0;
    let mut stack: Vec<FrameState> = Vec::new();

    while index < bytes.len() {
        match bytes[index] {
            b'<' => {
                if index + 1 >= bytes.len() {
                    break;
                }
                match bytes[index + 1] {
                    b'/' => {
                        index += 2;
                        while index < bytes.len() && bytes[index] != b'>' {
                            index += 1;
                        }
                        if index < bytes.len() {
                            index += 1;
                        }
                        if let Some(frame) = stack.pop() {
                            if frame.has_children {
                                output.push_str("</ul>");
                            }
                            output.push_str("</li>");
                        }
                    }
                    b'!' => {
                        index += 2;
                        while index + 2 < bytes.len()
                            && !(bytes[index] == b'-'
                                && bytes[index + 1] == b'-'
                                && bytes[index + 2] == b'>')
                        {
                            index += 1;
                        }
                        index = (index + 3).min(bytes.len());
                    }
                    b'?' => {
                        index += 2;
                        while index + 1 < bytes.len() && !(bytes[index] == b'?' && bytes[index + 1] == b'>') {
                            index += 1;
                        }
                        index = (index + 2).min(bytes.len());
                    }
                    _ => {
                        let start = index + 1;
                        let mut cursor = start;
                        while cursor < bytes.len() {
                            let ch = bytes[cursor];
                            if ch == b'/' || ch == b'>' || ch.is_ascii_whitespace() {
                                break;
                            }
                            cursor += 1;
                        }
                        if cursor > bytes.len() {
                            return Err("Malformed XML tag".into());
                        }
                        let tag_name = &xml[start..cursor];
                        let mut attrs: Vec<(String, String)> = Vec::new();
                        let mut self_closing = false;
                        let mut attr_cursor = cursor;
                        while attr_cursor < bytes.len() {
                            while attr_cursor < bytes.len() && bytes[attr_cursor].is_ascii_whitespace() {
                                attr_cursor += 1;
                            }
                            if attr_cursor >= bytes.len() {
                                break;
                            }
                            let ch = bytes[attr_cursor];
                            if ch == b'>' {
                                attr_cursor += 1;
                                break;
                            }
                            if ch == b'/' {
                                self_closing = true;
                                attr_cursor += 1;
                                if attr_cursor < bytes.len() && bytes[attr_cursor] == b'>' {
                                    attr_cursor += 1;
                                }
                                break;
                            }

                            let name_start = attr_cursor;
                            while attr_cursor < bytes.len()
                                && bytes[attr_cursor] != b'='
                                && !bytes[attr_cursor].is_ascii_whitespace()
                            {
                                attr_cursor += 1;
                            }
                            if attr_cursor >= bytes.len() {
                                return Err("Malformed attribute".into());
                            }
                            let name_end = attr_cursor;
                            while attr_cursor < bytes.len() && bytes[attr_cursor].is_ascii_whitespace() {
                                attr_cursor += 1;
                            }
                            if attr_cursor >= bytes.len() || bytes[attr_cursor] != b'=' {
                                return Err("Malformed attribute assignment".into());
                            }
                            attr_cursor += 1;
                            while attr_cursor < bytes.len() && bytes[attr_cursor].is_ascii_whitespace() {
                                attr_cursor += 1;
                            }
                            if attr_cursor >= bytes.len() {
                                return Err("Missing attribute value".into());
                            }
                            let quote = bytes[attr_cursor];
                            if quote != b'"' && quote != b'\'' {
                                return Err("Attribute value must be quoted".into());
                            }
                            attr_cursor += 1;
                            let value_start = attr_cursor;
                            while attr_cursor < bytes.len() && bytes[attr_cursor] != quote {
                                attr_cursor += 1;
                            }
                            if attr_cursor >= bytes.len() {
                                return Err("Unterminated attribute value".into());
                            }
                            let value_end = attr_cursor;
                            attr_cursor += 1;

                            let name = xml[name_start..name_end].trim();
                            let value = &xml[value_start..value_end];
                            attrs.push((name.to_string(), value.to_string()));
                        }
                        index = attr_cursor;

                        if let Some(parent) = stack.last_mut() {
                            if !parent.has_children {
                                parent.has_children = true;
                                output.push_str("<ul>");
                            }
                        }

                        output.push_str("<li>");
                        output.push_str(&escape_html(tag_name));
                        if !attrs.is_empty() {
                            output.push_str(" [");
                            for (idx, (name, value)) in attrs.iter().enumerate() {
                                if idx > 0 {
                                    output.push_str(", ");
                                }
                                output.push_str("<span class=\"attributes\">");
                                output.push_str(&escape_html(name));
                                output.push_str("</span>=<span class=\"text\">");
                                output.push('"');
                                output.push_str(&escape_html(value));
                                output.push('"');
                                output.push_str("</span>");
                            }
                            output.push_str("] ");
                        }

                        if self_closing {
                            output.push_str("</li>");
                        } else {
                            stack.push(FrameState::default());
                        }
                    }
                }
            }
            _ => {
                index += 1;
            }
        }
    }

    while let Some(frame) = stack.pop() {
        if frame.has_children {
            output.push_str("</ul>");
        }
        output.push_str("</li>");
    }

    output.push_str("</ul>");
    Ok(output)
}

#[no_mangle]
pub extern "C" fn lb_render_device_ui_html(xml_ptr: *const c_char) -> *mut c_char {
    if xml_ptr.is_null() {
        set_last_error("Null pointer received for XML input");
        return std::ptr::null_mut();
    }
    let c_slice = unsafe { CStr::from_ptr(xml_ptr) };
    match c_slice.to_str() {
        Ok(xml) => match render_device_ui_html(xml) {
            Ok(html) => match CString::new(html) {
                Ok(c_string) => {
                    clear_last_error();
                    c_string.into_raw()
                }
                Err(_) => {
                    set_last_error("Failed to allocate CString for HTML output");
                    std::ptr::null_mut()
                }
            },
            Err(err) => {
                set_last_error(err);
                std::ptr::null_mut()
            }
        },
        Err(_) => {
            set_last_error("XML input must be valid UTF-8");
            std::ptr::null_mut()
        }
    }
}

fn shlex_split(command: &str) -> Result<Vec<String>, String> {
    let mut parts: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut chars = command.chars().peekable();
    let mut in_single = false;
    let mut in_double = false;
    let mut escaped = false;

    while let Some(ch) = chars.next() {
        if escaped {
            current.push(ch);
            escaped = false;
            continue;
        }
        match ch {
            '\\' if !in_single => {
                escaped = true;
            }
            '\'' if !in_double => {
                in_single = !in_single;
            }
            '"' if !in_single => {
                in_double = !in_double;
            }
            ch if ch.is_whitespace() && !in_single && !in_double => {
                if !current.is_empty() {
                    parts.push(current.clone());
                    current.clear();
                }
            }
            _ => current.push(ch),
        }
    }

    if escaped {
        return Err("Trailing escape character".into());
    }
    if in_single || in_double {
        return Err("Unterminated quoted string".into());
    }
    if !current.is_empty() {
        parts.push(current);
    }
    Ok(parts)
}

fn execute_command(command: &str) -> Vec<String> {
    match shlex_split(command) {
        Ok(parts) => {
            if parts.is_empty() {
                return vec![String::new()];
            }
            let mut cmd = Command::new(&parts[0]);
            if parts.len() > 1 {
                cmd.args(&parts[1..]);
            }
            match cmd.output() {
                Ok(output) => {
                    let stdout = String::from_utf8_lossy(&output.stdout);
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    let mut lines: Vec<String> = stdout.lines().map(|line| line.to_string()).collect();
                    if !output.status.success() {
                        lines.push(format!("ERROR(exit={}): {}", output.status.code().unwrap_or(-1), stderr.trim()));
                    } else if !stderr.trim().is_empty() {
                        lines.push(format!("STDERR: {}", stderr.trim()));
                    }
                    if lines.is_empty() {
                        lines.push(String::new());
                    }
                    lines
                }
                Err(err) => vec![format!("ERROR(exec): {}", err)],
            }
        }
        Err(err) => vec![format!("ERROR(parse): {}", err)],
    }
}

const SCREENRECORD_STOP_TIMEOUT_SECS: u64 = 5;

#[no_mangle]
pub extern "C" fn lb_start_screen_record(serial_ptr: *const c_char, remote_path_ptr: *const c_char) -> i32 {
    if serial_ptr.is_null() || remote_path_ptr.is_null() {
        set_last_error("Null pointer provided to lb_start_screen_record");
        return 0;
    }

    let serial = match unsafe { CStr::from_ptr(serial_ptr) }.to_str() {
        Ok(value) => value.to_string(),
        Err(_) => {
            set_last_error("Serial must be valid UTF-8");
            return 0;
        }
    };

    let remote_path = match unsafe { CStr::from_ptr(remote_path_ptr) }.to_str() {
        Ok(value) => value.to_string(),
        Err(_) => {
            set_last_error("Remote path must be valid UTF-8");
            return 0;
        }
    };

    let registry = recording_registry();
    let mut guard = match registry.lock() {
        Ok(guard) => guard,
        Err(_) => {
            set_last_error("Recording registry is unavailable");
            return 0;
        }
    };

    if guard.contains_key(&serial) {
        set_last_error("Recording already active for serial");
        return 0;
    }

    match Command::new("adb")
        .args(["-s", &serial, "shell", "screenrecord", &remote_path])
        .spawn()
    {
        Ok(child) => {
            guard.insert(
                serial,
                RecordingHandle {
                    child,
                },
            );
            clear_last_error();
            1
        }
        Err(err) => {
            set_last_error(format!("Failed to spawn screenrecord: {}", err));
            0
        }
    }
}

#[no_mangle]
pub extern "C" fn lb_stop_screen_record(serial_ptr: *const c_char) -> i32 {
    if serial_ptr.is_null() {
        set_last_error("Null pointer provided to lb_stop_screen_record");
        return 0;
    }

    let serial = match unsafe { CStr::from_ptr(serial_ptr) }.to_str() {
        Ok(value) => value.to_string(),
        Err(_) => {
            set_last_error("Serial must be valid UTF-8");
            return 0;
        }
    };

    let registry = recording_registry();
    let mut guard = match registry.lock() {
        Ok(guard) => guard,
        Err(_) => {
            set_last_error("Recording registry is unavailable");
            return 0;
        }
    };

    let handle = guard.remove(&serial);
    drop(guard);

    let stop_output = Command::new("adb")
        .args(["-s", &serial, "shell", "pkill", "-SIGINT", "screenrecord"])
        .output();

    let mut had_error = false;
    if let Ok(output) = stop_output {
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            set_last_error(format!(
                "Failed to stop screenrecord cleanly: {}",
                stderr.trim()
            ));
            had_error = true;
        }
    } else if let Err(err) = stop_output {
        set_last_error(format!("Failed to invoke stop command: {}", err));
        had_error = true;
    }

    if let Some(mut recording) = handle {
        let timeout = Duration::from_secs(SCREENRECORD_STOP_TIMEOUT_SECS);
        let deadline = Instant::now() + timeout;
        loop {
            match recording.child.try_wait() {
                Ok(Some(_status)) => {
                    break;
                }
                Ok(None) => {
                    if Instant::now() >= deadline {
                        let _ = recording.child.kill();
                        let _ = recording.child.wait();
                        set_last_error("Timeout waiting for screenrecord process to exit");
                        return 0;
                    }
                    thread::sleep(Duration::from_millis(100));
                }
                Err(err) => {
                    set_last_error(format!("Failed to poll screenrecord process: {}", err));
                    return 0;
                }
            }
        }
    }

    if had_error {
        return 0;
    }

    clear_last_error();
    1
}

#[no_mangle]
pub extern "C" fn lb_run_commands_parallel(payload_ptr: *const c_char) -> *mut c_char {
    if payload_ptr.is_null() {
        set_last_error("Null payload passed to lb_run_commands_parallel");
        return std::ptr::null_mut();
    }

    let payload_cstr = unsafe { CStr::from_ptr(payload_ptr) };
    let payload = match payload_cstr.to_str() {
        Ok(value) => value,
        Err(_) => {
            set_last_error("Payload must be valid UTF-8");
            return std::ptr::null_mut();
        }
    };

    let mut lines = payload.lines();
    let count_line = match lines.next() {
        Some(value) => value.trim(),
        None => {
            set_last_error("Payload missing command count header");
            return std::ptr::null_mut();
        }
    };

    let command_count: usize = match count_line.parse() {
        Ok(value) => value,
        Err(_) => {
            set_last_error("Invalid command count in payload");
            return std::ptr::null_mut();
        }
    };

    let mut commands: Vec<String> = Vec::with_capacity(command_count);
    for _ in 0..command_count {
        match lines.next() {
            Some(cmd) => commands.push(cmd.to_string()),
            None => {
                set_last_error("Insufficient command lines in payload");
                return std::ptr::null_mut();
            }
        }
    }

    let mut handles = Vec::with_capacity(commands.len());
    for (index, command) in commands.into_iter().enumerate() {
        handles.push(std::thread::spawn(move || (index, execute_command(&command))));
    }

    let mut collected: Vec<(usize, Vec<String>)> = Vec::new();
    for handle in handles {
        match handle.join() {
            Ok(pair) => collected.push(pair),
            Err(_) => {
                set_last_error("Thread panicked during command execution");
                return std::ptr::null_mut();
            }
        }
    }
    collected.sort_by_key(|(index, _)| *index);

    let mut results: Vec<String> = Vec::new();
    for (_, lines) in collected.into_iter() {
        let joined = lines.join("\u{001f}");
        results.push(joined);
    }

    let combined = results.join("\u{001e}");
    match CString::new(combined) {
        Ok(c_string) => {
            clear_last_error();
            c_string.into_raw()
        }
        Err(_) => {
            set_last_error("Failed to build CString for command results");
            std::ptr::null_mut()
        }
    }
}
