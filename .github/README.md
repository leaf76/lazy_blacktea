# GitHub Actions Workflows

This directory contains automated workflows for building and testing Lazy Blacktea across multiple platforms.

## 🔄 Workflows

### 1. Build Multi-Platform Release (`build.yml`)

Automatically builds the application for:
- **macOS Intel (x86_64)** - Compatible with Intel-based Macs
- **macOS Apple Silicon (ARM64)** - Compatible with M1/M2/M3 Macs
- **Linux x86_64** - Compatible with most Linux distributions

#### Triggers:
- **Tags**: Pushes to tags starting with `v*` (e.g., `v1.0.0`)
- **Branches**: Pushes to `master` branch
- **Pull Requests**: PRs targeting `master` branch
- **Manual**: Via GitHub's "Run workflow" button with optional release creation

#### Outputs:
- **macOS**: `.dmg` disk images and `.zip` app bundles
- **Linux**: `.tar.gz` archives and `.AppImage` files
- **GitHub Releases**: Automatically created for tagged versions

#### Artifacts Retention:
- Build artifacts: 30 days
- Build logs (on failure): 7 days

### 2. Test and Validate (`test.yml`)

Runs comprehensive tests and validation across all platforms without creating releases.

#### Triggers:
- **Branches**: Pushes to `master` and feature/bugfix branches
- **Pull Requests**: PRs targeting `master` branch

#### Tests Include:
- **Platform Compatibility**: Tests on macOS Intel, Apple Silicon, and Linux
- **Import Tests**: Validates all Python modules can be imported
- **Startup Tests**: Ensures application starts without errors
- **Security Scan**: Dependency vulnerability checks with Safety and Bandit
- **Build Script Validation**: Verifies build scripts and PyInstaller specs
- **Dependency Analysis**: Checks for conflicts and generates dependency tree

## 🚀 Usage

### Creating a Release

1. **Tag-based Release** (Recommended):
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Manual Release**:
   - Go to Actions tab in GitHub
   - Select "Build Multi-Platform Release"
   - Click "Run workflow"
   - Check "Create GitHub Release" if desired

### Development Testing

- Tests run automatically on every push and PR
- Check the "Test and Validate" workflow for results
- Failed tests will block PR merging (if branch protection is enabled)

## 📦 Build Artifacts

### macOS Builds

**Intel (x86_64)**:
- `LazyBlacktea-macos-intel.dmg` - Disk image for easy installation
- `LazyBlacktea-macos-intel.zip` - Compressed app bundle

**Apple Silicon (ARM64)**:
- `LazyBlacktea-macos-arm64.dmg` - Disk image for M1/M2/M3 Macs
- `LazyBlacktea-macos-arm64.zip` - Compressed app bundle

### Linux Builds

**x86_64**:
- `lazyblacktea-linux-x86_64.tar.gz` - Traditional archive
- `LazyBlacktea-linux-x86_64.AppImage` - Portable executable

## 🔧 Environment Variables

The workflows use these key environment variables:

- `PYTHON_VERSION`: Python version to use (currently 3.11)
- `QT_QPA_PLATFORM`: Set to 'offscreen' for Linux headless testing
- `ARCHFLAGS`, `CFLAGS`, `LDFLAGS`: Architecture-specific build flags

## 🛠️ Local Development

To test builds locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the build script
python build.py

# Check output
ls -la dist/
```

## 📋 Requirements

### GitHub Repository Settings

1. **Actions Permissions**: Ensure GitHub Actions are enabled
2. **Token Permissions**: Default `GITHUB_TOKEN` has sufficient permissions for:
   - Creating releases
   - Uploading artifacts
   - Writing to packages (if needed)

### Build Dependencies

All dependencies are automatically installed by the workflows:

**Python**:
- PyQt6 >= 6.4.0
- PyInstaller >= 5.13.0
- setuptools >= 65.0.0

**System (Linux)**:
- python3-pyqt6
- python3-pyqt6.qtwidgets
- build-essential
- Various X11 libraries for GUI support

**System (macOS)**:
- Xcode command line tools (automatically available on GitHub runners)
- Homebrew (for additional dependencies if needed)

## 🔍 Troubleshooting

### Common Issues

1. **Build Failures**:
   - Check the build logs in the Actions tab
   - Verify all dependencies are correctly specified
   - Ensure PyInstaller spec files are valid

2. **Import Errors**:
   - Verify all required modules are in `requirements.txt`
   - Check for circular imports in the codebase

3. **Platform-Specific Issues**:
   - macOS: Code signing issues (may require developer certificates)
   - Linux: Missing system libraries (check apt-get install commands)

### Debug Steps

1. **Download Artifacts**: Failed builds upload logs as artifacts
2. **Check Test Results**: Review the "Test and Validate" workflow output
3. **Local Testing**: Run `python build.py` locally to reproduce issues

## 🎯 Best Practices

1. **Tagging**: Use semantic versioning for tags (e.g., `v1.2.3`)
2. **Branch Protection**: Enable required status checks for PRs
3. **Release Notes**: Tag commits include automatic release notes
4. **Testing**: Always test locally before pushing to master branch

## 📝 Workflow Maintenance

### Updating Dependencies

1. Update `requirements.txt` for Python dependencies
2. Update workflow files for system dependencies
3. Test changes in a feature branch before merging

### Adding New Platforms

To add Windows support:
1. Add Windows matrix entry to workflows
2. Create `build_windows.spec` PyInstaller spec
3. Update `build.py` with Windows-specific logic
4. Test thoroughly with Windows runners

## 🔐 Security

- **Dependency Scanning**: Automated with Safety and Bandit
- **Token Security**: Uses GitHub's built-in `GITHUB_TOKEN`
- **Artifact Isolation**: Each platform builds in isolated environments

## 📞 Support

For workflow-related issues:
1. Check the Actions tab for detailed logs
2. Review this documentation
3. Create an issue with workflow logs attached
4. Tag maintainers for assistance

---

These workflows are designed to provide reliable, automated builds across all supported platforms. They leverage the existing `build.py` script and PyInstaller configurations for consistency with local development.