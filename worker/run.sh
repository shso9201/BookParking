#!/bin/bash

# Update package list and install prerequisites
echo "Installing prerequisites..."
apt update
apt install -y libopencv-dev libtesseract-dev git cmake build-essential libleptonica-dev liblog4cplus-dev libcurl3-dev beanstalkd

# Clone the OpenALPR repository
echo "Cloning OpenALPR repository..."
git clone https://github.com/openalpr/openalpr.git

# Navigate to the OpenALPR source directory
cd openalpr/src

# Create the build directory
echo "Setting up build directory..."
mkdir build
cd build

# Setup the compile environment
echo "Setting up compile environment..."
# cmake -DCMAKE_INSTALL_PREFIX:PATH=/usr -DCMAKE_INSTALL_SYSCONFDIR:PATH=/etc ..
cmake -DTesseract_INCLUDE_DIRS=/usr/include/tesseract \
      -DTesseract_INCLUDE_CCMAIN_DIR=/usr/include/tesseract \
      -DTesseract_INCLUDE_CCUTIL_DIR=/usr/include/tesseract \
      -DTesseract_LIBRARIES=/usr/lib/aarch64-linux-gnu/libtesseract.so ..

# Compile the library
echo "Compiling OpenALPR..."
make

# Install the binaries and libraries
echo "Installing OpenALPR..."
make install

echo "/usr/local/lib/" | tee /etc/ld.so.conf.d/openalpr.conf
ldconfig