/**
 * Electron Main Process
 *
 * Responsibilities:
 * - Create browser window with Next.js UI
 * - Spawn and manage Python backend process
 * - Handle IPC communication
 * - Manage app lifecycle
 */

import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

// =============================================================================
// Configuration
// =============================================================================

const isDev = process.env.NODE_ENV !== 'production';
const BACKEND_PORT = 8000;
const FRONTEND_URL = isDev ? 'http://localhost:3000' : `file://${path.join(__dirname, '../.next/server/app/index.html')}`;

// =============================================================================
// Global State
// =============================================================================

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

// =============================================================================
// Python Backend Management
// =============================================================================

function getBackendPath(): string {
  if (isDev) {
    // Development: backend is in sibling directory
    return path.join(__dirname, '../../backend');
  } else {
    // Production: backend is bundled in resources
    return path.join(process.resourcesPath, 'backend');
  }
}

function getPythonExecutable(): string {
  // Try to find Python in common locations
  const candidates = [
    'python3',
    'python',
    '/usr/bin/python3',
    '/usr/local/bin/python3',
    '/opt/homebrew/bin/python3',
  ];

  for (const candidate of candidates) {
    try {
      const result = require('child_process').execSync(`which ${candidate}`, { encoding: 'utf8' });
      if (result.trim()) {
        return result.trim();
      }
    } catch {
      // Try next candidate
    }
  }

  return 'python3'; // Default fallback
}

async function startPythonBackend(): Promise<void> {
  const backendPath = getBackendPath();
  const pythonExe = getPythonExecutable();

  console.log(`Starting Python backend from: ${backendPath}`);
  console.log(`Using Python: ${pythonExe}`);

  // Check if backend directory exists
  if (!fs.existsSync(backendPath)) {
    console.error(`Backend directory not found: ${backendPath}`);
    return;
  }

  pythonProcess = spawn(
    pythonExe,
    ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    {
      cwd: backendPath,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    }
  );

  pythonProcess.stdout?.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });

  pythonProcess.stderr?.on('data', (data) => {
    console.error(`[Backend] ${data.toString().trim()}`);
  });

  pythonProcess.on('error', (error) => {
    console.error('Failed to start Python backend:', error);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python backend exited with code ${code}, signal ${signal}`);
    pythonProcess = null;
  });

  // Wait for backend to be ready
  await waitForBackend();
}

async function waitForBackend(maxAttempts = 30): Promise<boolean> {
  const http = require('http');

  for (let i = 0; i < maxAttempts; i++) {
    try {
      await new Promise<void>((resolve, reject) => {
        const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/api/health`, (res: any) => {
          if (res.statusCode === 200) {
            resolve();
          } else {
            reject(new Error(`Status ${res.statusCode}`));
          }
        });
        req.on('error', reject);
        req.setTimeout(1000, () => {
          req.destroy();
          reject(new Error('Timeout'));
        });
      });
      console.log('Backend is ready!');
      return true;
    } catch {
      console.log(`Waiting for backend... (${i + 1}/${maxAttempts})`);
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  console.error('Backend failed to start');
  return false;
}

function stopPythonBackend(): void {
  if (pythonProcess) {
    console.log('Stopping Python backend...');
    pythonProcess.kill('SIGTERM');

    // Force kill after timeout
    setTimeout(() => {
      if (pythonProcess) {
        pythonProcess.kill('SIGKILL');
      }
    }, 5000);
  }
}

// =============================================================================
// Window Management
// =============================================================================

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 1200,
    minHeight: 700,
    title: 'Aura',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 15, y: 15 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Load the app
  if (isDev) {
    mainWindow.loadURL(FRONTEND_URL);
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../out/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// =============================================================================
// IPC Handlers
// =============================================================================

function setupIpcHandlers(): void {
  // Get backend URL
  ipcMain.handle('get-backend-url', () => {
    return `http://127.0.0.1:${BACKEND_PORT}`;
  });

  // Open project dialog
  ipcMain.handle('open-project', async () => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      properties: ['openDirectory'],
      title: 'Open LaTeX Project',
      message: 'Select a LaTeX project directory',
    });

    if (!result.canceled && result.filePaths.length > 0) {
      return result.filePaths[0];
    }
    return null;
  });

  // Create new project dialog
  ipcMain.handle('new-project', async (_event, name: string) => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      properties: ['openDirectory', 'createDirectory'],
      title: 'Choose Location for New Project',
    });

    if (!result.canceled && result.filePaths.length > 0) {
      const projectPath = path.join(result.filePaths[0], name);

      // Create project directory
      if (!fs.existsSync(projectPath)) {
        fs.mkdirSync(projectPath, { recursive: true });
      }

      return projectPath;
    }
    return null;
  });

  // Get projects directory
  ipcMain.handle('get-projects-dir', () => {
    const homeDir = app.getPath('home');
    const projectsDir = path.join(homeDir, 'aura-projects');

    // Create if doesn't exist
    if (!fs.existsSync(projectsDir)) {
      fs.mkdirSync(projectsDir, { recursive: true });
    }

    return projectsDir;
  });
}

// =============================================================================
// App Lifecycle
// =============================================================================

app.whenReady().then(async () => {
  console.log('Aura starting...');

  // Start backend first
  await startPythonBackend();

  // Setup IPC
  setupIpcHandlers();

  // Create window
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopPythonBackend();
});

app.on('quit', () => {
  stopPythonBackend();
});
