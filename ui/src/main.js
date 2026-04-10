// Electron main process for Smart Search
// Windows-compatible with Ctrl+Space hotkey

const { app, BrowserWindow, globalShortcut, ipcMain, shell, dialog, Tray, Menu, nativeImage } = require('electron');
const path = require('path');

let mainWindow = null;
let tray = null;
const API_URL = 'http://127.0.0.1:8765';

// Create system tray
function createTray() {
  const fs = require('fs');
  
  // Try to find icon file
  const possiblePaths = [
    path.join(__dirname, 'tray-icon.png'),
    path.join(__dirname, '..', 'src', 'tray-icon.png')
  ];
  
  let icon = null;
  
  for (const iconPath of possiblePaths) {
    try {
      if (fs.existsSync(iconPath)) {
        const tempIcon = nativeImage.createFromPath(iconPath);
        if (!tempIcon.isEmpty()) {
          icon = tempIcon;
          console.log('Loaded tray icon from:', iconPath);
          break;
        }
      }
    } catch (e) {
      console.log('Icon path not found:', iconPath);
    }
  }
  
  // Fallback: create icon programmatically
  if (!icon || icon.isEmpty()) {
    console.log('Creating fallback tray icon');
    const size = 16;
    const buffer = Buffer.alloc(size * size * 4);
    for (let i = 0; i < size * size; i++) {
      const x = i % size;
      const y = Math.floor(i / size);
      const dx = x - 7.5, dy = y - 7.5;
      const dist = Math.sqrt(dx*dx + dy*dy);
      if (dist < 6) {
        buffer[i*4] = 0;
        buffer[i*4+1] = 120;
        buffer[i*4+2] = 255;
        buffer[i*4+3] = 255;
      }
    }
    icon = nativeImage.createFromBuffer(buffer, { width: size, height: size });
  }
  
  tray = new Tray(icon);
  tray.setToolTip('Smart Search - Ctrl+Space to search');
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open Search',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    {
      label: 'Index Files',
      click: async () => {
        try {
          await fetch(`${API_URL}/index`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recrawl: true })
          });
        } catch (e) {
          console.error('Index failed:', e);
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);
  
  tray.setContextMenu(contextMenu);
  
  // Double-click to open search
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// Create the main window (Spotlight-like)
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 600,
    height: 450,
    frame: false,  // Frameless window
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Load the renderer HTML
  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  // Hide when focus is lost (like Spotlight)
  mainWindow.on('blur', () => {
    if (!mainWindow.isDestroyed()) {
      mainWindow.hide();
    }
  });

  // Log when window is ready
  mainWindow.once('ready-to-show', () => {
    console.log('Smart Search UI ready');
  });
}

// Register global Ctrl+Space hotkey
function registerHotkey() {
  const ret = globalShortcut.register('CommandOrControl+Space', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
        // Send message to renderer to focus search input
        mainWindow.webContents.send('focus-search');
      }
    }
  });

  if (!ret) {
    console.log('Failed to register global shortcut');
  } else {
    console.log('Global shortcut Ctrl+Space registered');
  }
}

// App ready
app.whenReady().then(() => {
  createWindow();
  createTray();  // Create system tray
  registerHotkey();

  // Check if started with --hidden flag (auto-start)
  const startedHidden = process.argv.includes('--hidden');
  if (startedHidden) {
    // Don't show window - run in background
    console.log('Started minimized to tray');
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Handle window close - minimize to tray instead of quitting
app.on('window-all-closed', (event) => {
  // Don't quit on Windows, minimize to tray
  if (process.platform === 'win32' && !app.isQuitting) {
    event.preventDefault();
    if (mainWindow) {
      mainWindow.hide();
    }
  }
});

// Handle before quit - allow actual quit
app.on('before-quit', () => {
  app.isQuitting = true;
});

// Toggle auto-start with Windows
ipcMain.handle('set-auto-launch', async (event, enable) => {
  app.setLoginItemSettings({
    openAtLogin: enable,
    path: app.getPath('exe'),
    args: ['--hidden']
  });
  return { success: true };
});

// ==============================================================================
// IPC Handlers for backend communication
// ==============================================================================

// Search handler
ipcMain.handle('search', async (event, query) => {
  try {
    const response = await fetch(`${API_URL}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query, top_k: 10 })
    });
    return await response.json();
  } catch (error) {
    console.error('Search error:', error);
    return { error: error.message };
  }
});

// Status handler
ipcMain.handle('get-status', async () => {
  try {
    const response = await fetch(`${API_URL}/status`);
    return await response.json();
  } catch (error) {
    console.error('Status error:', error);
    return { error: error.message };
  }
});

// Index handler
ipcMain.handle('start-index', async () => {
  try {
    const response = await fetch(`${API_URL}/index`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    return await response.json();
  } catch (error) {
    console.error('Index error:', error);
    return { error: error.message };
  }
});

// Open file handler
ipcMain.handle('open-file', async (event, filePath) => {
  try {
    await shell.openPath(filePath);
    return { success: true };
  } catch (error) {
    console.error('Open file error:', error);
    return { error: error.message };
  }
});

// Show in folder handler
ipcMain.handle('show-in-folder', async (event, filePath) => {
  try {
    shell.showItemInFolder(filePath);
    return { success: true };
  } catch (error) {
    console.error('Show in folder error:', error);
    return { error: error.message };
  }
});

// Preview handler
ipcMain.handle('preview-file', async (event, filePath) => {
  try {
    const response = await fetch(`${API_URL}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: filePath })
    });
    return await response.json();
  } catch (error) {
    console.error('Preview error:', error);
    return { error: error.message };
  }
});

// Hide window handler
ipcMain.handle('hide-window', async () => {
  if (mainWindow) {
    mainWindow.hide();
  }
});
