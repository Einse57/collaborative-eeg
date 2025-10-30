# Remote Access Setup Guide

This guide explains how to enable remote clients to access the collaborative EEG annotation platform.

## Current Architecture

The system uses **in-memory storage** for datasets and annotations. This means:
- ✅ Multiple users on the **same computer** can share data (same server instance)
- ❌ Users on **different computers** see separate data (different server instances or memory spaces)

## Quick Fix: Single Server with Network Access

### Step 1: Find Your Computer's IP Address

On Windows PowerShell:
```powershell
ipconfig
```

Look for "IPv4 Address" under your active network adapter (e.g., `192.168.1.100`)

### Step 2: Configure the Frontend for Remote Access

Edit `frontend/.env`:
```env
# Replace <YOUR_IP> with your computer's IP address
VITE_API_URL=http://<YOUR_IP>:8000
```

Example:
```env
VITE_API_URL=http://192.168.1.100:8000
```

### Step 3: Configure Windows Firewall

Run the provided script (as Administrator):
```powershell
.\configure-firewall.ps1
```

Or manually allow ports:
- **Port 8000** - Backend API (FastAPI)
- **Port 5173** - Frontend Dev Server (Vite)

### Step 4: Start the Application

```powershell
.\start.ps1
```

### Step 5: Remote Clients Connect

Remote users should:

1. **Edit their local `.env` file** to point to your server:
   ```env
   VITE_API_URL=http://<SERVER_IP>:8000
   ```

2. **Access the frontend** at:
   - `http://<SERVER_IP>:5173` (if using the server's frontend)
   - OR run their own frontend locally (connected to the remote backend)

## Important Limitations

⚠️ **Current Setup Limitations:**

1. **Server Restart = Data Loss**: All datasets and annotations are in RAM
2. **Single Server Instance**: Only works if all clients connect to the same running server
3. **No Persistence**: Uploaded files are saved, but the mapping is lost on restart
4. **Network Security**: No authentication or encryption (for development only)

## Production Solutions

For production use with true multi-user remote access, implement one of these:

### Option 1: Database Backend (Recommended)

Use PostgreSQL or MongoDB to store:
- Dataset metadata
- Annotation data
- User information

**Pros:** Persistent, scalable, supports multiple servers
**Cons:** Requires database setup

### Option 2: Redis for Shared State

Use Redis as an in-memory database that multiple server instances can share.

**Pros:** Fast, easy to set up, persistent (with RDB/AOF)
**Cons:** Still in-memory, single point of failure

### Option 3: Cloud Storage + Database

Store files in S3/Azure Blob + metadata in database.

**Pros:** Scalable, reliable, supports large files
**Cons:** More complex, costs money

## Troubleshooting

### Remote clients can't see datasets

**Symptom**: Local client sees datasets, remote clients see empty list

**Causes**:
1. Remote client's `.env` points to wrong IP
2. Firewall blocking port 8000
3. Multiple server instances running

**Solutions**:
1. Verify `.env` has correct `VITE_API_URL`
2. Check Windows Firewall allows port 8000
3. Stop all servers, start only one instance
4. Use `http://<IP>:8000` not `localhost:8000` for remote access

### Annotations don't sync

**Symptom**: Creating annotation on one client doesn't show on another

**Causes**:
1. Socket.IO connection failed
2. Different dataset instances
3. CORS issues

**Solutions**:
1. Check browser console for Socket.IO errors
2. Ensure both clients selected the same dataset
3. Backend CORS should allow all origins (already configured)

### Server crashes on dataset load

**Symptom**: Error when clicking dataset after server restart

**Cause**: Dataset in `datasets_db` but file not loaded into MNE

**Solution**: Fixed in latest version - datasets auto-reload from file

## Network Security Notes

⚠️ **For Development/Lab Use Only**

Current setup:
- ✅ CORS allows all origins
- ❌ No authentication
- ❌ No HTTPS/encryption
- ❌ No rate limiting

**For production**, add:
- User authentication (JWT tokens)
- HTTPS (SSL certificates)
- Rate limiting
- Input validation
- Access control lists (ACLs)

## Next Steps

For a robust multi-user system, see `docs/DATABASE_MIGRATION.md` for implementing persistent storage with PostgreSQL.
