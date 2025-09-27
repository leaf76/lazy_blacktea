"""Adb objects models."""

from typing import Optional


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
