"""Recording synchronization manager for logcat-recording integration.

Manages the synchronization between logcat logs and recording sessions,
allowing automatic export of logs corresponding to recording time windows.
"""

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from utils.common import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from ui.logcat_viewer import LogcatListModel, LogLine


@dataclass
class RecordingSession:
    """Represents a recording session with associated log data."""

    recording_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    start_log_index: int = 0
    end_log_index: Optional[int] = None
    recording_method: str = "adb"  # "scrcpy" or "adb"
    video_file_path: Optional[str] = None
    log_file_path: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Get the duration of the recording in seconds."""
        if self.end_time is None:
            return (datetime.now() - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()

    @property
    def is_active(self) -> bool:
        """Check if the recording session is still active."""
        return self.end_time is None


class RecordingSyncManager(QObject):
    """Manages synchronization between logcat logs and recording sessions.

    This class tracks recording sessions and their corresponding log indices,
    allowing automatic export of logs for the recording time window.

    Signals:
        session_started: Emitted when a new recording session starts
        session_stopped: Emitted when a recording session stops
        logs_exported: Emitted when logs are exported (session_id, log_path)
    """

    session_started = pyqtSignal(str)  # recording_id
    session_stopped = pyqtSignal(str, str)  # recording_id, video_path
    logs_exported = pyqtSignal(str, str)  # recording_id, log_path

    def __init__(
        self,
        log_model: "LogcatListModel",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._log_model = log_model
        self._sessions: Dict[str, RecordingSession] = {}
        self._active_session_id: Optional[str] = None

    @property
    def has_active_session(self) -> bool:
        """Check if there's an active recording session."""
        return self._active_session_id is not None

    @property
    def active_session(self) -> Optional[RecordingSession]:
        """Get the currently active session, if any."""
        if self._active_session_id:
            return self._sessions.get(self._active_session_id)
        return None

    def start_session(
        self,
        method: str = "adb",
        recording_id: Optional[str] = None,
    ) -> RecordingSession:
        """Begin a synchronized recording session.

        Args:
            method: Recording method ("scrcpy" or "adb")
            recording_id: Optional custom ID, auto-generated if not provided

        Returns:
            The created RecordingSession

        Raises:
            RuntimeError: If a session is already active
        """
        if self._active_session_id is not None:
            raise RuntimeError("A recording session is already active")

        if recording_id is None:
            recording_id = str(uuid.uuid4())[:8]

        session = RecordingSession(
            recording_id=recording_id,
            start_time=datetime.now(),
            start_log_index=self._log_model.rowCount(),
            recording_method=method,
        )

        self._sessions[recording_id] = session
        self._active_session_id = recording_id

        self.session_started.emit(recording_id)
        return session

    def stop_session(
        self,
        video_path: Optional[str] = None,
        recording_id: Optional[str] = None,
    ) -> Optional[RecordingSession]:
        """End a recording session and capture final log index.

        Args:
            video_path: Path to the recorded video file
            recording_id: Session ID to stop (defaults to active session)

        Returns:
            The stopped RecordingSession, or None if not found
        """
        session_id = recording_id or self._active_session_id
        if session_id is None:
            return None

        session = self._sessions.get(session_id)
        if session is None:
            return None

        session.end_time = datetime.now()
        session.end_log_index = self._log_model.rowCount()
        session.video_file_path = video_path

        if self._active_session_id == session_id:
            self._active_session_id = None

        self.session_stopped.emit(session_id, video_path or "")
        return session

    def export_session_logs(
        self,
        session: RecordingSession,
        output_dir: Optional[str] = None,
    ) -> Optional[str]:
        """Export logs for the session time range to a file.

        Args:
            session: The recording session to export logs for
            output_dir: Output directory (defaults to video file directory)

        Returns:
            Path to the exported log file, or None if export failed
        """
        if session.start_log_index is None:
            return None

        # Determine output directory
        if output_dir is None and session.video_file_path:
            output_dir = os.path.dirname(session.video_file_path)

        if output_dir is None:
            return None

        # Get logs for the session time range
        all_logs = self._log_model.to_list()
        end_index = session.end_log_index or len(all_logs)
        session_logs: List["LogLine"] = all_logs[session.start_log_index:end_index]

        # Generate filename
        if session.video_file_path:
            video_base = os.path.splitext(os.path.basename(session.video_file_path))[0]
            log_filename = f"{video_base}_logcat.txt"
        else:
            timestamp = session.start_time.strftime("%Y%m%d_%H%M%S")
            log_filename = f"recording_{timestamp}_logcat.txt"

        log_path = os.path.join(output_dir, log_filename)

        # Write logs
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                self._write_log_header(f, session)
                for log in session_logs:
                    f.write(log.raw + "\n")
        except OSError as e:
            logger.warning("Failed to export session logs to %s: %s", log_path, e)
            return None

        session.log_file_path = log_path
        self.logs_exported.emit(session.recording_id, log_path)
        return log_path

    def _write_log_header(self, f, session: RecordingSession) -> None:
        """Write metadata header to log file."""
        f.write("# Recording Session Logcat Export\n")
        f.write(f"# Recording ID: {session.recording_id}\n")
        f.write(f"# Method: {session.recording_method}\n")
        f.write(f"# Start: {session.start_time.isoformat()}\n")
        if session.end_time:
            f.write(f"# End: {session.end_time.isoformat()}\n")
            f.write(f"# Duration: {session.duration_seconds:.1f} seconds\n")
        if session.video_file_path:
            f.write(f"# Video: {session.video_file_path}\n")
        f.write(f"# Log entries: {(session.end_log_index or 0) - session.start_log_index}\n")
        f.write("#" + "=" * 60 + "\n\n")

    def get_session(self, recording_id: str) -> Optional[RecordingSession]:
        """Get a session by ID."""
        return self._sessions.get(recording_id)

    def get_all_sessions(self) -> List[RecordingSession]:
        """Get all recorded sessions."""
        return list(self._sessions.values())

    def clear_sessions(self) -> None:
        """Clear all completed sessions (keeps active session)."""
        if self._active_session_id:
            active = self._sessions.get(self._active_session_id)
            self._sessions = {self._active_session_id: active} if active else {}
        else:
            self._sessions = {}
