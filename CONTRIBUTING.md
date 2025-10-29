# Contributing to EEG/MEG Annotation Platform

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help create a welcoming environment for all contributors

## How to Contribute

### Reporting Bugs

1. **Check existing issues** - Search to see if the bug has already been reported
2. **Create a detailed report** - Include:
   - Operating system and version
   - Python version
   - Node.js version
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Screenshots if applicable
   - Error messages and stack traces

### Suggesting Features

1. **Check existing feature requests** - Avoid duplicates
2. **Provide clear use cases** - Explain why the feature would be useful
3. **Consider scope** - Is it aligned with the project goals?

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch** - `git checkout -b feature/your-feature-name`
3. **Make your changes**
4. **Test thoroughly** - Ensure both backend and frontend work
5. **Follow code style** - Python: PEP 8, JavaScript: ESLint
6. **Write clear commit messages**
7. **Submit the pull request**

## Development Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- Git

### Setup Steps

1. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/eeg-annotation-platform.git
   cd eeg-annotation-platform
   ```

2. **Backend setup:**
   ```bash
   cd backend
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

3. **Frontend setup:**
   ```bash
   cd frontend
   npm install
   ```

4. **Run tests:**
   ```bash
   # Backend (when tests are added)
   cd backend
   pytest

   # Frontend (when tests are added)
   cd frontend
   npm test
   ```

## Code Style Guidelines

### Python (Backend)
- Follow PEP 8
- Use type hints where appropriate
- Write docstrings for functions and classes
- Keep functions focused and small
- Use meaningful variable names

Example:
```python
def load_annotations(self, raw: mne.io.Raw) -> List[Dict]:
    """Extract annotations from Raw object"""
    if raw.annotations is None:
        return []
    # ... implementation
```

### JavaScript (Frontend)
- Use modern ES6+ syntax
- Prefer const/let over var
- Use meaningful component and variable names
- Keep components focused
- Add comments for complex logic

Example:
```javascript
const handleAnnotationCreate = async (annotation) => {
  // Broadcast to other users via Socket.IO
  socket.emit('annotation_created', {
    ...annotation,
    dataset_id: currentDataset.id
  })
}
```

### File Organization
- **Backend:** Services handle business logic, routes handle HTTP
- **Frontend:** Components are self-contained, App.jsx manages global state
- **Shared:** Constants and utilities in separate files

## Testing

### Backend Testing (TODO)
```python
# tests/test_mne_service.py
def test_load_file():
    service = MNEService()
    raw, dataset_id = service.load_file('sample.fif')
    assert raw is not None
    assert dataset_id == 'sample'
```

### Frontend Testing (TODO)
```javascript
// src/components/__tests__/SignalViewer.test.jsx
test('renders signal viewer', () => {
  render(<SignalViewer signalData={mockData} />)
  expect(screen.getByRole('canvas')).toBeInTheDocument()
})
```

## Commit Message Guidelines

Use clear, descriptive commit messages:

```
feat: Add annotation import from CSV files
fix: Resolve canvas rendering offset issue
docs: Update network setup instructions
refactor: Extract signal normalization into separate function
perf: Optimize channel rendering for large datasets
test: Add unit tests for MNE service
```

Prefixes:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding tests
- `chore`: Maintenance tasks

## Project Structure

```
eeg-annotation-platform/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # HTTP endpoints
│   │   ├── services/         # Business logic
│   │   ├── core/            # Configuration
│   │   └── main.py          # FastAPI app
│   └── tests/               # Backend tests
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── App.jsx          # Main app
│   │   └── main.jsx         # Entry point
│   └── tests/               # Frontend tests
└── docs/                    # Additional documentation
```

## Areas for Contribution

### High Priority
- [ ] User authentication system
- [ ] Database integration (PostgreSQL)
- [ ] Unit and integration tests
- [ ] Annotation editing (resize/move)
- [ ] Performance optimization for large datasets

### Medium Priority
- [ ] Signal processing features (filtering, re-referencing)
- [ ] Keyboard shortcuts
- [ ] Channel selection UI
- [ ] Annotation templates
- [ ] Export to additional formats

### Low Priority
- [ ] Dark mode
- [ ] Internationalization (i18n)
- [ ] Mobile responsive design
- [ ] Alternative visualization modes

## Questions?

- **Documentation:** Check the README.md and wiki
- **Issues:** Open a GitHub issue for questions
- **Discussions:** Use GitHub Discussions for general questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
