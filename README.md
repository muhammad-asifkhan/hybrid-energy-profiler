# ⚡ Hybrid Energy Profiler

A sophisticated Linux process energy profiling tool that combines user-space monitoring with kernel-level data collection to provide real-time energy consumption analysis.

## 🌟 Features

- **Real-time Process Monitoring**: Continuous monitoring of all running processes with auto-refresh
- **Hybrid Data Collection**: Combines `/proc` filesystem with optional eBPF kernel tracing
- **Energy Scoring Algorithm**: Advanced formula-based energy consumption estimation
- **Process Classification**: Intelligent categorization (CPU-bound, IO-bound, Memory-bound, Context-heavy, Mixed, Resource-Heavy)
- **Web Dashboard**: Modern, responsive interface with real-time updates
- **Data Export**: Multiple format exports (CSV, JSON, TXT)
- **Visualization**: Automatic generation of energy consumption graphs
- **Advanced Filtering**: Filter by name, CPU%, memory, and classification
- **Historical Tracking**: SQLite database for process metrics history
- **Alerting System**: Real-time anomaly detection with configurable rules
- **Authentication**: Optional user authentication and role-based access control
- **Docker Support**: Containerized deployment with Docker Compose
- **Unit Tests**: Comprehensive test suite for core modules

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch dashboard (opens automatically in browser)
python3 run.py
```

The dashboard will open at `http://localhost:5000` with all features available.

## 📋 Requirements

- Python 3.8+
- Linux (uses `/proc` filesystem)
- Optional: BCC (BPF Compiler Collection) for kernel tracing

## 📦 Installation

### Basic Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd "Operating system project"

# Install Python dependencies
pip install -r requirements.txt
```

### Optional: Kernel Tracing Support

For enhanced kernel-level metrics (context switches, syscalls):

```bash
# Install BCC (Ubuntu/Debian)
sudo apt-get install python3-bpfcc

# Or use the installation script
chmod +x install_kernel_support.sh
./install_kernel_support.sh
```

**Note:** The profiler works perfectly without kernel tracing. Kernel tracing adds additional metrics for more accuracy.

## 🎯 Usage

### Web Dashboard (Recommended)

```bash
python3 run.py
```

The dashboard provides:
- Real-time process monitoring (auto-refreshes every 5 seconds)
- Interactive filtering and sorting
- Process classification statistics
- Energy insights and recommendations
- Export capabilities
- Graph generation

### API Endpoints

- `GET /api/data` - Get current process metrics (JSON)
- `GET /api/export?format=csv|json|txt` - Export data
- `GET /api/generate-graphs` - Generate visualization graphs
- `GET /api/history/trends/<process_name>` - Get historical trends
- `GET /health` - Health check endpoint

## 🏗️ Project Structure

```
Operating system project/
├── energymon/              # Main project module
│   ├── __init__.py
│   ├── collector.py        # Process metrics collection
│   ├── model.py            # Energy model & classification
│   ├── dashboard.py        # Flask web dashboard
│   ├── tracer.py           # eBPF kernel tracing
│   ├── exporter.py         # Data export functions
│   ├── visualizer.py       # Graph generation
│   ├── config.py           # Configuration management
│   ├── logger.py           # Structured logging
│   ├── storage.py           # SQLite data persistence
│   ├── auth.py             # Authentication & authorization
│   └── alerts.py            # Alerting system
├── tests/                  # Unit tests
├── data/                   # SQLite database (auto-created)
├── logs/                   # Application logs
├── output/                 # Exports and graphs
│   ├── exports/
│   └── graphs/
├── config.json            # Configuration file
├── requirements.txt       # Python dependencies
├── run.py                 # Main entry point
├── Dockerfile             # Docker containerization
├── docker-compose.yml     # Docker Compose setup
└── README.md              # This file
```

## ⚙️ Configuration

Edit `config.json` to customize:

- **Collection settings**: Interval, filters, max processes
- **Energy model**: Weights, adaptive adjustment
- **Dashboard**: Host, port, debug mode
- **Storage**: Database path, retention period
- **Logging**: Level, file size, rotation
- **Security**: Authentication, rate limiting

## 🔬 Energy Calculation Model

The energy score is calculated using:

```
E = w1×CPU + w2×IO + w3×Memory + w4×ContextSwitches + w5×Syscalls
```

**Base Weights:**
- CPU: 0.6 (highest impact)
- I/O: 0.3 (significant energy cost)
- Memory: 0.1 (lower direct impact)
- Context Switches: 0.2 (kernel overhead)
- Syscalls: 0.1 (kernel transition overhead)

**Note:** This is a relative energy estimation model for process comparison, not absolute energy measurement. For production use, consider integrating with hardware power measurement APIs (RAPL, perf, etc.).

## 🧪 Testing

```bash
# Run all tests
python3 tests/run_tests.py

# Run specific test module
python3 -m pytest tests/test_model.py
```

## 🐳 Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t hybrid-energy-profiler .
docker run -p 5000:5000 hybrid-energy-profiler
```

## 📊 Process Classifications

- **CPU-bound**: High CPU usage, low I/O
- **IO-bound**: High I/O activity
- **Memory-bound**: Large memory footprint
- **Context-heavy**: Frequent task switching
- **Mixed**: Balanced resource usage
- **Resource-Heavy**: High usage across all resources

## 🔒 Security

- Optional authentication (disabled by default)
- Rate limiting on API endpoints
- Configurable CORS and allowed hosts
- Session management with secure cookies

## 📝 License

This project is provided as-is for educational and research purposes.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📚 Documentation

For detailed technical documentation, see `Hybrid_Energy_Profiler_Complete_Documentation.md`.

## ⚠️ Important Notes

- **Energy Formula**: The energy calculation is an estimation model for relative process comparison, not absolute energy measurement
- **Permissions**: Some features may require elevated permissions for kernel tracing
- **Platform**: Designed for Linux systems using the `/proc` filesystem

## 🐛 Troubleshooting

- **Dashboard not loading**: Check if port 5000 is available
- **No processes shown**: Verify you have permission to read `/proc`
- **Kernel tracing errors**: Install BCC or use user-space mode only
- **Database errors**: Check `data/` directory permissions

## 📞 Support

For issues and questions, please open an issue on GitHub.

## 👨‍💻 Author

**Muhammad Asif Khan**

- 🎓 Data Science student at Institute of Management Sciences, Peshawar
- 💻 Experienced in Web Development, Mobile App Development, and Machine Learning
- 📧 Email: [asifcalm53@gmail.com](mailto:asifcalm53@gmail.com)
- 🔗 GitHub: [@muhammad-asifkhan](https://github.com/muhammad-asifkhan)
- 💼 LinkedIn: [Muhammad Asif Khan](https://www.linkedin.com/in/muhammad-asif-khan-334a37260/)
- 📍 Based in Peshawar, Pakistan

---

**Made with ⚡ for Linux system administrators and researchers**
