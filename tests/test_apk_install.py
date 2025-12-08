"""Tests for the APK installation module."""

import tempfile
import pathlib
import zipfile
import unittest
from unittest.mock import patch, MagicMock

from utils import adb_models, adb_tools


class ApkInstallErrorCodeTests(unittest.TestCase):
    """Tests for ApkInstallErrorCode enum."""

    def test_success_from_output(self):
        """Test parsing SUCCESS from output."""
        output = "Performing Streamed Install\nSuccess"
        code = adb_models.ApkInstallErrorCode.from_output(output)
        self.assertEqual(code, adb_models.ApkInstallErrorCode.SUCCESS)

    def test_success_case_insensitive(self):
        """Test SUCCESS detection is case insensitive."""
        output = "success"
        code = adb_models.ApkInstallErrorCode.from_output(output)
        self.assertEqual(code, adb_models.ApkInstallErrorCode.SUCCESS)

    def test_version_downgrade_error(self):
        """Test parsing INSTALL_FAILED_VERSION_DOWNGRADE."""
        output = "Failure [INSTALL_FAILED_VERSION_DOWNGRADE]"
        code = adb_models.ApkInstallErrorCode.from_output(output)
        self.assertEqual(code, adb_models.ApkInstallErrorCode.INSTALL_FAILED_VERSION_DOWNGRADE)

    def test_insufficient_storage_error(self):
        """Test parsing INSTALL_FAILED_INSUFFICIENT_STORAGE."""
        output = "Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]"
        code = adb_models.ApkInstallErrorCode.from_output(output)
        self.assertEqual(code, adb_models.ApkInstallErrorCode.INSTALL_FAILED_INSUFFICIENT_STORAGE)

    def test_older_sdk_error(self):
        """Test parsing INSTALL_FAILED_OLDER_SDK."""
        output = "INSTALL_FAILED_OLDER_SDK: requires API level 30"
        code = adb_models.ApkInstallErrorCode.from_output(output)
        self.assertEqual(code, adb_models.ApkInstallErrorCode.INSTALL_FAILED_OLDER_SDK)

    def test_unknown_error_empty_output(self):
        """Test UNKNOWN_ERROR for empty output."""
        code = adb_models.ApkInstallErrorCode.from_output("")
        self.assertEqual(code, adb_models.ApkInstallErrorCode.UNKNOWN_ERROR)

    def test_unknown_error_unrecognized_output(self):
        """Test UNKNOWN_ERROR for unrecognized output."""
        output = "Some random error message"
        code = adb_models.ApkInstallErrorCode.from_output(output)
        self.assertEqual(code, adb_models.ApkInstallErrorCode.UNKNOWN_ERROR)

    def test_error_code_has_description(self):
        """Test error codes have descriptions."""
        for member in adb_models.ApkInstallErrorCode:
            self.assertIsNotNone(member.description)
            self.assertIsInstance(member.description, str)
            self.assertTrue(len(member.description) > 0)


class ApkInfoTests(unittest.TestCase):
    """Tests for ApkInfo dataclass."""

    def test_is_valid_with_package_name(self):
        """Test is_valid returns True when package_name is set."""
        info = adb_models.ApkInfo(path="/test.apk", package_name="com.example")
        self.assertTrue(info.is_valid)

    def test_is_valid_with_error(self):
        """Test is_valid returns False when error is set."""
        info = adb_models.ApkInfo(path="/test.apk", error="File not found")
        self.assertFalse(info.is_valid)

    def test_is_valid_no_package_name(self):
        """Test is_valid returns False without package_name."""
        info = adb_models.ApkInfo(path="/test.apk")
        self.assertFalse(info.is_valid)


class ApkInstallResultTests(unittest.TestCase):
    """Tests for ApkInstallResult dataclass."""

    def test_error_message_on_success(self):
        """Test error_message is empty on success."""
        result = adb_models.ApkInstallResult(
            serial="123",
            success=True,
            error_code=adb_models.ApkInstallErrorCode.SUCCESS
        )
        self.assertEqual(result.error_message, "")

    def test_error_message_on_failure(self):
        """Test error_message returns description on failure."""
        result = adb_models.ApkInstallResult(
            serial="123",
            success=False,
            error_code=adb_models.ApkInstallErrorCode.INSTALL_FAILED_INSUFFICIENT_STORAGE
        )
        self.assertIn("storage", result.error_message.lower())

    def test_display_message_success(self):
        """Test display_message on success."""
        result = adb_models.ApkInstallResult(
            serial="123",
            success=True,
            error_code=adb_models.ApkInstallErrorCode.SUCCESS,
            device_model="Pixel 7"
        )
        self.assertIn("Pixel 7", result.display_message)
        self.assertIn("Successfully", result.display_message)


class ApkBatchInstallResultTests(unittest.TestCase):
    """Tests for ApkBatchInstallResult dataclass."""

    def test_counts(self):
        """Test successful_count and failed_count."""
        batch = adb_models.ApkBatchInstallResult(apk_path="/test.apk")
        batch.results["dev1"] = adb_models.ApkInstallResult(
            serial="dev1", success=True, error_code=adb_models.ApkInstallErrorCode.SUCCESS
        )
        batch.results["dev2"] = adb_models.ApkInstallResult(
            serial="dev2", success=False, error_code=adb_models.ApkInstallErrorCode.UNKNOWN_ERROR
        )
        batch.results["dev3"] = adb_models.ApkInstallResult(
            serial="dev3", success=True, error_code=adb_models.ApkInstallErrorCode.SUCCESS
        )

        self.assertEqual(batch.successful_count, 2)
        self.assertEqual(batch.failed_count, 1)
        self.assertEqual(batch.total_count, 3)
        self.assertFalse(batch.all_successful)

    def test_all_successful(self):
        """Test all_successful property."""
        batch = adb_models.ApkBatchInstallResult(apk_path="/test.apk")
        batch.results["dev1"] = adb_models.ApkInstallResult(
            serial="dev1", success=True, error_code=adb_models.ApkInstallErrorCode.SUCCESS
        )
        batch.results["dev2"] = adb_models.ApkInstallResult(
            serial="dev2", success=True, error_code=adb_models.ApkInstallErrorCode.SUCCESS
        )

        self.assertTrue(batch.all_successful)

    def test_get_failed_devices(self):
        """Test get_failed_devices method."""
        batch = adb_models.ApkBatchInstallResult(apk_path="/test.apk")
        batch.results["dev1"] = adb_models.ApkInstallResult(
            serial="dev1", success=True, error_code=adb_models.ApkInstallErrorCode.SUCCESS
        )
        batch.results["dev2"] = adb_models.ApkInstallResult(
            serial="dev2", success=False, error_code=adb_models.ApkInstallErrorCode.UNKNOWN_ERROR
        )

        failed = batch.get_failed_devices()
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].serial, "dev2")


class GetApkInfoTests(unittest.TestCase):
    """Tests for get_apk_info function."""

    def test_file_not_found(self):
        """Test error when file doesn't exist."""
        info = adb_tools.get_apk_info("/nonexistent/file.apk")
        self.assertFalse(info.is_valid)
        self.assertIn("not found", info.error.lower())

    def test_valid_apk_structure(self):
        """Test valid APK with AndroidManifest.xml."""
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            apk_path = f.name

        try:
            # Create a minimal valid APK (ZIP with AndroidManifest.xml)
            with zipfile.ZipFile(apk_path, 'w') as zf:
                zf.writestr('AndroidManifest.xml', '<manifest/>')
                zf.writestr('classes.dex', 'fake dex content')

            info = adb_tools.get_apk_info(apk_path)
            self.assertIsNone(info.error)
            self.assertTrue(info.file_size_bytes > 0)
        finally:
            pathlib.Path(apk_path).unlink(missing_ok=True)

    def test_invalid_zip_file(self):
        """Test error for non-ZIP file."""
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            f.write(b"not a zip file")
            apk_path = f.name

        try:
            info = adb_tools.get_apk_info(apk_path)
            self.assertFalse(info.is_valid)
            self.assertIn("not a valid ZIP", info.error)
        finally:
            pathlib.Path(apk_path).unlink(missing_ok=True)

    def test_missing_manifest(self):
        """Test error when AndroidManifest.xml is missing."""
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            apk_path = f.name

        try:
            with zipfile.ZipFile(apk_path, 'w') as zf:
                zf.writestr('classes.dex', 'fake dex')

            info = adb_tools.get_apk_info(apk_path)
            self.assertFalse(info.is_valid)
            self.assertIn("AndroidManifest.xml", info.error)
        finally:
            pathlib.Path(apk_path).unlink(missing_ok=True)

    def test_split_apk_bundle_detected(self):
        """Test .apks file is detected as split APK."""
        with tempfile.NamedTemporaryFile(suffix=".apks", delete=False) as f:
            apk_path = f.name

        try:
            # Create a minimal .apks bundle
            with zipfile.ZipFile(apk_path, 'w') as zf:
                zf.writestr('base.apk', 'fake apk')

            info = adb_tools.get_apk_info(apk_path)
            self.assertTrue(info.is_split_apk)
        finally:
            pathlib.Path(apk_path).unlink(missing_ok=True)


class ExtractSplitApksTests(unittest.TestCase):
    """Tests for extract_split_apks function."""

    def test_extract_apks_bundle(self):
        """Test extracting APKs from .apks bundle."""
        with tempfile.NamedTemporaryFile(suffix=".apks", delete=False) as f:
            bundle_path = f.name

        try:
            # Create a mock .apks bundle
            with zipfile.ZipFile(bundle_path, 'w') as zf:
                zf.writestr('base.apk', 'base content')
                zf.writestr('split_config.arm64_v8a.apk', 'arm64 content')
                zf.writestr('split_config.en.apk', 'en content')

            with tempfile.TemporaryDirectory() as extract_dir:
                apk_paths = adb_tools.extract_split_apks(bundle_path, extract_dir)

                self.assertEqual(len(apk_paths), 3)
                # base.apk should be first due to sorting
                self.assertIn('base.apk', apk_paths[0])
        finally:
            pathlib.Path(bundle_path).unlink(missing_ok=True)

    def test_regular_apk_returns_single_path(self):
        """Test regular .apk returns itself as single path."""
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            apk_path = f.name

        try:
            apk_paths = adb_tools.extract_split_apks(apk_path)
            self.assertEqual(len(apk_paths), 1)
            self.assertEqual(apk_paths[0], apk_path)
        finally:
            pathlib.Path(apk_path).unlink(missing_ok=True)

    def test_nonexistent_bundle_returns_empty(self):
        """Test nonexistent bundle returns empty list."""
        apk_paths = adb_tools.extract_split_apks("/nonexistent.apks")
        self.assertEqual(apk_paths, [])


class ValidateApkForDeviceTests(unittest.TestCase):
    """Tests for validate_apk_for_device function."""

    def test_valid_apk_no_device_check(self):
        """Test valid APK without device API level check."""
        info = adb_models.ApkInfo(path="/test.apk", package_name="com.example")
        valid, error = adb_tools.validate_apk_for_device(info)
        self.assertTrue(valid)
        self.assertEqual(error, "")

    def test_invalid_apk_with_error(self):
        """Test invalid APK with error."""
        info = adb_models.ApkInfo(path="/test.apk", error="Invalid APK")
        valid, error = adb_tools.validate_apk_for_device(info)
        self.assertFalse(valid)
        self.assertIn("Invalid APK", error)

    def test_device_api_level_too_low(self):
        """Test device API level below minimum SDK."""
        info = adb_models.ApkInfo(
            path="/test.apk",
            package_name="com.example",
            min_sdk_version=30
        )
        valid, error = adb_tools.validate_apk_for_device(info, device_api_level=28)
        self.assertFalse(valid)
        self.assertIn("API level", error)

    def test_device_api_level_sufficient(self):
        """Test device API level meets minimum SDK."""
        info = adb_models.ApkInfo(
            path="/test.apk",
            package_name="com.example",
            min_sdk_version=28
        )
        valid, error = adb_tools.validate_apk_for_device(info, device_api_level=30)
        self.assertTrue(valid)


class InstallApkTests(unittest.TestCase):
    """Tests for install_apk function."""

    @patch('utils.adb_tools.common.run_command')
    def test_successful_install_single_device(self, mock_run):
        """Test successful installation on single device."""
        mock_run.return_value = "Success"

        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            apk_path = f.name
            # Create valid APK
            with zipfile.ZipFile(apk_path, 'w') as zf:
                zf.writestr('AndroidManifest.xml', '<manifest/>')
                zf.writestr('classes.dex', 'fake')

        try:
            result = adb_tools.install_apk(["device1"], apk_path, validate=False)

            self.assertEqual(result.total_count, 1)
            self.assertEqual(result.successful_count, 1)
            self.assertTrue(result.all_successful)
            self.assertTrue(result.results["device1"].success)
        finally:
            pathlib.Path(apk_path).unlink(missing_ok=True)

    @patch('utils.adb_tools.common.run_command')
    def test_install_multiple_devices(self, mock_run):
        """Test installation on multiple devices."""
        # Return success for all calls
        mock_run.return_value = "Success"

        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            apk_path = f.name
            # Create valid APK
            with zipfile.ZipFile(apk_path, 'w') as zf:
                zf.writestr('AndroidManifest.xml', '<manifest/>')
                zf.writestr('classes.dex', 'fake')

        try:
            result = adb_tools.install_apk(
                ["device1", "device2", "device3"],
                apk_path,
                validate=False
            )

            self.assertEqual(result.total_count, 3)
            self.assertEqual(result.successful_count, 3)
        finally:
            pathlib.Path(apk_path).unlink(missing_ok=True)

    @patch('utils.adb_tools.common.run_command')
    def test_install_with_failure(self, mock_run):
        """Test handling of installation failure."""
        mock_run.return_value = "Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]"

        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            apk_path = f.name
            with zipfile.ZipFile(apk_path, 'w') as zf:
                zf.writestr('AndroidManifest.xml', '<manifest/>')
                zf.writestr('classes.dex', 'fake')

        try:
            result = adb_tools.install_apk(["device1"], apk_path, validate=False)

            self.assertEqual(result.failed_count, 1)
            self.assertEqual(
                result.results["device1"].error_code,
                adb_models.ApkInstallErrorCode.INSTALL_FAILED_INSUFFICIENT_STORAGE
            )
        finally:
            pathlib.Path(apk_path).unlink(missing_ok=True)

    def test_install_file_not_found(self):
        """Test error when APK file doesn't exist."""
        result = adb_tools.install_apk(["device1"], "/nonexistent.apk", validate=False)

        self.assertEqual(result.failed_count, 1)
        self.assertFalse(result.results["device1"].success)

    @patch('utils.adb_tools.common.run_command')
    def test_progress_callback_called(self, mock_run):
        """Test progress callback is called for each device."""
        mock_run.return_value = "Success"
        callback_calls = []

        def progress_callback(serial, current, total, success):
            callback_calls.append((serial, current, total, success))

        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            apk_path = f.name
            with zipfile.ZipFile(apk_path, 'w') as zf:
                zf.writestr('AndroidManifest.xml', '<manifest/>')
                zf.writestr('classes.dex', 'fake')

        try:
            result = adb_tools.install_apk(
                ["device1", "device2"],
                apk_path,
                validate=False,
                progress_callback=progress_callback
            )

            # Callback should be called for each device
            self.assertEqual(len(callback_calls), 2)
        finally:
            pathlib.Path(apk_path).unlink(missing_ok=True)


class ParseAaptOutputTests(unittest.TestCase):
    """Tests for _parse_aapt_output function."""

    def test_parse_package_info(self):
        """Test parsing package name, version code, and version name."""
        output = """package: name='com.example.app' versionCode='123' versionName='1.2.3' compileSdkVersion='33'
sdkVersion:'21'
targetSdkVersion:'33'"""

        info = adb_models.ApkInfo(path="/test.apk")
        adb_tools._parse_aapt_output(info, output)

        self.assertEqual(info.package_name, "com.example.app")
        self.assertEqual(info.version_code, 123)
        self.assertEqual(info.version_name, "1.2.3")
        self.assertEqual(info.min_sdk_version, 21)
        self.assertEqual(info.target_sdk_version, 33)

    def test_parse_empty_output(self):
        """Test parsing empty output doesn't crash."""
        info = adb_models.ApkInfo(path="/test.apk")
        adb_tools._parse_aapt_output(info, "")

        self.assertIsNone(info.package_name)
        self.assertIsNone(info.version_code)


if __name__ == '__main__':
    unittest.main()
