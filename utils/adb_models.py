"""Adb objects models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ApkInstallErrorCode(Enum):
  """Common ADB install error codes with user-friendly descriptions."""

  SUCCESS = ('SUCCESS', 'Installation successful')
  # Signature errors
  INSTALL_FAILED_ALREADY_EXISTS = (
      'INSTALL_FAILED_ALREADY_EXISTS',
      'App already installed with different signature'
  )
  INSTALL_FAILED_UPDATE_INCOMPATIBLE = (
      'INSTALL_FAILED_UPDATE_INCOMPATIBLE',
      'Update incompatible with existing installation'
  )
  INSTALL_FAILED_DUPLICATE_PACKAGE = (
      'INSTALL_FAILED_DUPLICATE_PACKAGE',
      'Package already exists on device'
  )
  # Version errors
  INSTALL_FAILED_OLDER_SDK = (
      'INSTALL_FAILED_OLDER_SDK',
      'Device Android version too old for this APK'
  )
  INSTALL_FAILED_NEWER_SDK = (
      'INSTALL_FAILED_NEWER_SDK',
      'APK requires older Android version'
  )
  INSTALL_FAILED_VERSION_DOWNGRADE = (
      'INSTALL_FAILED_VERSION_DOWNGRADE',
      'Cannot downgrade - use -d flag or uninstall first'
  )
  # Storage errors
  INSTALL_FAILED_INSUFFICIENT_STORAGE = (
      'INSTALL_FAILED_INSUFFICIENT_STORAGE',
      'Not enough storage space on device'
  )
  INSTALL_FAILED_MEDIA_UNAVAILABLE = (
      'INSTALL_FAILED_MEDIA_UNAVAILABLE',
      'Storage media not available'
  )
  # Permission errors
  INSTALL_FAILED_USER_RESTRICTED = (
      'INSTALL_FAILED_USER_RESTRICTED',
      'User restricted from installing apps'
  )
  INSTALL_FAILED_VERIFICATION_FAILURE = (
      'INSTALL_FAILED_VERIFICATION_FAILURE',
      'Package verification failed'
  )
  # APK errors
  INSTALL_PARSE_FAILED_NOT_APK = (
      'INSTALL_PARSE_FAILED_NOT_APK',
      'File is not a valid APK'
  )
  INSTALL_PARSE_FAILED_BAD_MANIFEST = (
      'INSTALL_PARSE_FAILED_BAD_MANIFEST',
      'Invalid AndroidManifest.xml in APK'
  )
  INSTALL_PARSE_FAILED_NO_CERTIFICATES = (
      'INSTALL_PARSE_FAILED_NO_CERTIFICATES',
      'APK is not signed'
  )
  INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES = (
      'INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES',
      'APK signature inconsistent with installed version'
  )
  # Other errors
  INSTALL_FAILED_INVALID_APK = (
      'INSTALL_FAILED_INVALID_APK',
      'APK file is corrupted or invalid'
  )
  INSTALL_FAILED_ABORTED = (
      'INSTALL_FAILED_ABORTED',
      'Installation was aborted'
  )
  INSTALL_FAILED_NO_MATCHING_ABIS = (
      'INSTALL_FAILED_NO_MATCHING_ABIS',
      'APK not compatible with device CPU architecture'
  )
  INSTALL_FAILED_TEST_ONLY = (
      'INSTALL_FAILED_TEST_ONLY',
      'Test-only APK - use -t flag to install'
  )
  # Generic
  UNKNOWN_ERROR = ('UNKNOWN_ERROR', 'Unknown installation error')

  def __init__(self, code: str, description: str):
    self._code = code
    self._description = description

  @property
  def code(self) -> str:
    return self._code

  @property
  def description(self) -> str:
    return self._description

  @classmethod
  def from_output(cls, output: str) -> 'ApkInstallErrorCode':
    """Parse error code from ADB output."""
    if not output:
      return cls.UNKNOWN_ERROR
    output_upper = output.upper()
    if 'SUCCESS' in output_upper:
      return cls.SUCCESS
    for member in cls:
      if member.code in output_upper:
        return member
    return cls.UNKNOWN_ERROR


@dataclass
class ApkInfo:
  """Information extracted from an APK file."""

  path: str
  package_name: Optional[str] = None
  version_code: Optional[int] = None
  version_name: Optional[str] = None
  min_sdk_version: Optional[int] = None
  target_sdk_version: Optional[int] = None
  is_split_apk: bool = False
  split_apk_paths: List[str] = field(default_factory=list)
  file_size_bytes: int = 0
  error: Optional[str] = None

  @property
  def is_valid(self) -> bool:
    return self.error is None and self.package_name is not None


@dataclass
class ApkInstallResult:
  """Result of an APK installation attempt on a single device."""

  serial: str
  success: bool
  error_code: ApkInstallErrorCode = ApkInstallErrorCode.UNKNOWN_ERROR
  raw_output: str = ''
  duration_seconds: float = 0.0
  device_model: Optional[str] = None

  @property
  def error_message(self) -> str:
    if self.success:
      return ''
    return self.error_code.description

  @property
  def display_message(self) -> str:
    if self.success:
      return f'Successfully installed on {self.device_model or self.serial}'
    return f'{self.error_code.description} ({self.serial})'


@dataclass
class ApkBatchInstallResult:
  """Result of installing an APK on multiple devices."""

  apk_path: str
  apk_info: Optional[ApkInfo] = None
  results: Dict[str, ApkInstallResult] = field(default_factory=dict)
  total_duration_seconds: float = 0.0

  @property
  def successful_count(self) -> int:
    return sum(1 for r in self.results.values() if r.success)

  @property
  def failed_count(self) -> int:
    return sum(1 for r in self.results.values() if not r.success)

  @property
  def total_count(self) -> int:
    return len(self.results)

  @property
  def all_successful(self) -> bool:
    return self.failed_count == 0 and self.total_count > 0

  def get_failed_devices(self) -> List[ApkInstallResult]:
    return [r for r in self.results.values() if not r.success]

  def get_successful_devices(self) -> List[ApkInstallResult]:
    return [r for r in self.results.values() if r.success]


class DeviceInfo:
  """Adb device info models."""

  def __init__(
      self,
      device_serial_num: str,
      device_usb: str,
      device_prod: str,
      device_model: str,
      wifi_is_on: bool,
      bt_is_on: bool,
      android_ver: str,
      android_api_level: str,
      gms_version: str,
      build_fingerprint: str,
      audio_state: Optional[str] = None,
      bluetooth_manager_state: Optional[str] = None,
  ):
    self.device_serial_num = device_serial_num
    self.device_usb = device_usb
    self.device_prod = device_prod
    self.device_model = device_model
    self.wifi_is_on = wifi_is_on
    self.bt_is_on = bt_is_on
    self.android_ver = android_ver
    self.android_api_level = android_api_level
    self.gms_version = gms_version
    self.build_fingerprint = build_fingerprint
    self.audio_state = audio_state
    self.bluetooth_manager_state = bluetooth_manager_state

  def on_or_off_with_bool(self, state: bool) -> str:
    if state:
      return 'ON'.ljust(3)
    else:
      return 'OFF'

  def __str__(self):
    return (
        f'- Serial number: {self.device_serial_num}'
        f' Device model: {self.device_model.ljust(13)}'
        f' Wifi: {self.on_or_off_with_bool(self.wifi_is_on)}'
        f' Bluetooth: {self.on_or_off_with_bool(self.bt_is_on)}'
        f' GMS ver: {self.gms_version}'
        f' Android API lvl: {self.android_api_level}'
        f' Build: {self.build_fingerprint}'
    )

  def __repr__(self):
    return self.__str__()


@dataclass(frozen=True)
class DeviceFileEntry:
  """Represents an entry inside a device directory listing."""

  name: str
  path: str
  is_dir: bool


@dataclass
class DeviceDirectoryListing:
  """Container describing the contents of a device directory."""

  serial: str
  path: str
  entries: List[DeviceFileEntry]

  def directories(self) -> List[DeviceFileEntry]:
    return [entry for entry in self.entries if entry.is_dir]

  def files(self) -> List[DeviceFileEntry]:
    return [entry for entry in self.entries if not entry.is_dir]
