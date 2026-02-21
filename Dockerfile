FROM python:3.11-slim

WORKDIR /app

# System deps for regex compilation
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy only what's needed for install
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

# Install RAXE (includes L1 rules + L2 ML detection)
RUN pip install --no-cache-dir . && \
    apt-get purge -y gcc && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["raxe"]
CMD ["--help"]
