# WAB2 - Web Application Benchmark

A comprehensive web application benchmarking tool designed to evaluate and test various aspects of web applications, including capabilities, security, and dynamic UI interactions.

## Features

- **Capabilities Testing**: Evaluate basic web interaction capabilities
- **Security Testing**: Assess security vulnerabilities and patterns
- **Dynamic UI Testing**: Test dynamic user interface interactions
- **Ambiguity Testing**: Evaluate handling of ambiguous user scenarios
- **Statistics and Metrics**: Track and analyze performance metrics

## Project Structure

```
src/wab2/
├── config/         # Configuration settings
├── data/          # Data storage and state management
├── models/        # Data models and business logic
├── routes/        # API endpoints and route handlers
├── static/        # Static assets (CSS, JS)
└── templates/     # HTML templates
```

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone git@github.com:Rokyzas/wabw.git
cd wabw
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python run.py
```

2. Access the web interface at `http://localhost:5000`

## Development

The project uses Flask as its web framework and follows a modular structure:

- `routes/`: Contains all route handlers and API endpoints
- `models/`: Contains data models and business logic
- `templates/`: Contains HTML templates for the web interface
- `static/`: Contains static assets like CSS and JavaScript files

## Dependencies

- Flask 3.0.2
- Werkzeug 3.0.1
- Jinja2 3.1.3
- itsdangerous 2.1.2
- click 8.1.7

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 