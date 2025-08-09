# Using AFTIS with Syncthing Directory

This example shows how to configure AFTIS to monitor your Syncthing directory at `/var/syncthing/eStatement/`.

## Configuration Steps

1. **Create your `.env` file** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file** to configure the Syncthing directory:
   ```bash
   # Use your Syncthing directory for PDF files
   INBOX_HOST_PATH=/var/syncthing/eStatement
   INBOX_PATH=/srv/aftis/inbox

   # Other configurations...
   AFTIS_PORT=8080
   POSTGRES_PORT=5432
   AUTO_DELETE_PDFS=true
   ```

3. **Ensure directory permissions**:
   ```bash
   # Make sure the directory exists and is accessible
   sudo mkdir -p /var/syncthing/eStatement
   sudo chown $USER:$USER /var/syncthing/eStatement
   chmod 755 /var/syncthing/eStatement
   ```

4. **Start the services**:
   ```bash
   ./start.sh
   ```

## How it works

- `INBOX_HOST_PATH=/var/syncthing/eStatement`: This is your host directory where Syncthing syncs the PDF files
- `INBOX_PATH=/srv/aftis/inbox`: This is the path inside the Docker containers (usually doesn't need to be changed)
- The Docker volume mount maps your host directory to the container directory
- The auto-processor monitors your Syncthing directory and processes PDFs automatically

## Verification

After starting, you should see:
```
📁 Drop PDF files in: /var/syncthing/eStatement/
```

Now when Syncthing syncs new PDF files to `/var/syncthing/eStatement/`, they will be automatically processed by AFTIS.

## Directory Structure

```
/var/syncthing/eStatement/     # Your Syncthing directory (monitored)
├── statement1.pdf        # Auto-processed
├── statement2.pdf        # Auto-processed
└── ...

/your/project/            # AFTIS project directory  
├── .env                  # Your configuration
├── docker-compose.yml    # Uses INBOX_HOST_PATH
└── ...
```