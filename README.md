# modulus-cli

Simple CLI to connect your local repository with Modulus for indexing.

## Install

```bash
pip install modulus-cli
```

## Quick Start

```bash
modulus login --api-key <your-api-key>
modulus repo index <path-to-your-repo>
```

## Commands

### Login

```bash
modulus login --api-key <your-api-key>
```

Saves your API key locally after verification.

### Index a repository

```bash
modulus repo index <path-to-your-repo>
```

Scans the repository and starts an indexing job.
