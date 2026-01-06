# Base image with TeX Live
FROM texlive/texlive:latest

# Install basic tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Default command to keep container running or run a build script
CMD ["/bin/bash"]
