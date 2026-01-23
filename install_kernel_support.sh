#!/bin/bash
# Install kernel support for enhanced energy monitoring

echo "🔧 Installing kernel support for Hybrid Energy Profiler..."
echo "This will install BCC (eBPF) for kernel-level monitoring"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script requires sudo privileges for kernel header installation"
    echo "Please run with: sudo ./install_kernel_support.sh"
    exit 1
fi

# Update package list
echo "📦 Updating package list..."
apt update

# Install kernel headers and build tools
echo "🔨 Installing kernel headers and build tools..."
apt install -y linux-headers-$(uname -r) build-essential

# Install BCC tools
echo "📊 Installing BCC (eBPF) tools..."
apt install -y python3-bcc bcc-tools

# Install additional dependencies
echo "📚 Installing additional dependencies..."
pip3 install bcc

# Verify installation
echo "✅ Verifying installation..."
python3 -c "
try:
    from bcc import BPF
    print('✅ BCC installation successful!')
    print('🚀 eBPF kernel monitoring is now available')
except ImportError as e:
    print(f'❌ BCC import failed: {e}')
    print('Please check the installation above')
"

echo
echo "🎉 Installation complete!"
echo "📋 The energy profiler will now use eBPF for kernel-level monitoring"
echo "🔄 Restart the dashboard to see enhanced kernel data collection"
echo
echo "If you encounter any issues:"
echo "- Make sure kernel headers match your running kernel: $(uname -r)"
echo "- Check if your system supports eBPF (most modern Linux kernels do)"
echo "- Run the dashboard with sudo if you encounter permission issues"
