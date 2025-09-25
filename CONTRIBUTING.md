# Contributing to Lazy Blacktea

Thank you for your interest in contributing to Lazy Blacktea! This document provides guidelines for contributors.

> **Current Project Version:** v0.0.11

## 🐛 Reporting Bugs

1. **Check existing issues** to avoid duplicates
2. **Use the bug report template** when creating new issues
3. **Include system information**:
   - OS version
   - Python version
   - ADB version
   - Application version
4. **Provide steps to reproduce** the issue
5. **Include screenshots** if applicable

## 🚀 Feature Requests

1. **Check existing feature requests** to avoid duplicates
2. **Describe the feature** and its use case
3. **Explain why it would be valuable** to other users
4. **Consider implementation complexity**

## 💻 Code Contributions

### Setting up Development Environment

1. **Fork the repository**
2. **Clone your fork**:
   ```bash
   git clone https://github.com/yourusername/lazy_blacktea.git
   cd lazy_blacktea
   ```
3. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Development Guidelines

- **Code Style**: Follow PEP 8 and use type hints
- **Testing**: Add tests for new features and bug fixes
- **Documentation**: Update README and docstrings as needed
- **Commit Messages**: Use clear, descriptive commit messages
- **Branch Naming**: Use descriptive branch names (feature/, bugfix/, hotfix/)

### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/amazing-feature
   ```
2. **Follow coding standards**:
   - Use type hints
   - Follow PEP 8 style guide
   - Add docstrings to functions
   - Include unit tests for new features
3. **Test your changes**:
   ```bash
   python -m unittest tests.test_refactored_features tests.test_performance tests.test_edge_cases
   ```
4. **Commit your changes**:
   ```bash
   git commit -m "Add amazing feature"
   ```
5. **Push to your fork**:
   ```bash
   git push origin feature/amazing-feature
   ```
6. **Open a Pull Request**

## 🔍 Code Review Process

1. All PRs require review before merging
2. Ensure CI tests pass
3. Address reviewer feedback
4. Maintain backwards compatibility when possible

## 📋 Testing

Run the comprehensive test suite:

```bash
# Run all tests
python -m unittest tests.test_refactored_features tests.test_performance tests.test_edge_cases -v

# Run specific test categories
python -m unittest tests.test_refactored_features -v  # Core functionality
python -m unittest tests.test_performance -v         # Performance tests
python -m unittest tests.test_edge_cases -v          # Edge cases
```

## 🤝 Community Guidelines

- **Be respectful** and inclusive
- **Help others** when you can
- **Share your experience** and improvements
- **Follow the Code of Conduct**

## 📞 Getting Help

- 📖 **Documentation**: Check README and inline code documentation
- 🐛 **Issues**: [GitHub Issues](https://github.com/yourusername/lazy_blacktea/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/yourusername/lazy_blacktea/discussions)

Thank you for contributing! 🍵✨
