const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const fse = require('fs-extra');
const glob = require('glob');
const Terser = require('terser');
const CleanCSS = require('clean-css');

// Paths
const FRONTEND_DIR = path.join(__dirname, 'Code/frontend');
const BACKEND_UI_DIR = path.join(__dirname, 'Code/backend/UI');
const DIST_UI_DIR = path.join(__dirname, 'Code/backend/dist/UI');
const BACKEND_DIR = path.join(__dirname, 'Code/backend');
const DIST_DIR = path.join(__dirname, 'Code/backend/dist');

// Helper: Minify JS
function minifyJS(filePath) {
  const code = fs.readFileSync(filePath, 'utf8');
  const result = Terser.minify(code);
  if (result.error) throw result.error;
  return result.code;
}

// Helper: Minify CSS
function minifyCSS(filePath) {
  const code = fs.readFileSync(filePath, 'utf8');
  return new CleanCSS().minify(code).styles;
}

// 1. Minify all frontend JS and CSS
function minifyFrontend() {
  // Minify JS
  const jsFiles = glob.sync(path.join(FRONTEND_DIR, '**/*.js'));
  jsFiles.forEach(jsFile => {
    const minified = minifyJS(jsFile);
    fs.writeFileSync(jsFile, minified, 'utf8');
  });
  // Minify CSS
  const cssFiles = glob.sync(path.join(FRONTEND_DIR, '**/*.css'));
  cssFiles.forEach(cssFile => {
    const minified = minifyCSS(cssFile);
    fs.writeFileSync(cssFile, minified, 'utf8');
  });
}

// 2. Copy all frontend HTML and assets to /backend/UI
function copyFrontendToBackendUI() {
  fse.ensureDirSync(BACKEND_UI_DIR);
  fse.copySync(FRONTEND_DIR, BACKEND_UI_DIR, { overwrite: true });
}

// 3. Create dist/UI and copy frontend files
function copyUIToDist() {
  fse.ensureDirSync(DIST_UI_DIR);
  fse.copySync(BACKEND_UI_DIR, DIST_UI_DIR, { overwrite: true });
}

// Clean dist folder before build
function cleanDist() {
  if (fse.existsSync(DIST_DIR)) {
    fse.emptyDirSync(DIST_DIR);
  } else {
    fse.ensureDirSync(DIST_DIR);
  }
}

// 4. Copy Python files, wifi.dat, and ota/version.json to /backend/dist
function copyPythonToDist() {
  fse.ensureDirSync(DIST_DIR);
  // Copy all .py files
  const pyFiles = glob.sync(path.join(BACKEND_DIR, '**/*.py'));
  pyFiles.forEach(pyFile => {
    const rel = path.relative(BACKEND_DIR, pyFile);
    const dest = path.join(DIST_DIR, rel);
    fse.ensureDirSync(path.dirname(dest));
    fse.copyFileSync(pyFile, dest);
  });
  // Copy wifi.dat if exists
  const wifiDat = path.join(BACKEND_DIR, 'wifi.dat');
  if (fs.existsSync(wifiDat)) {
    fse.copyFileSync(wifiDat, path.join(DIST_DIR, 'wifi.dat'));
  }
  // Copy ota/version.json if exists
  const otaVersionSrc = path.join(BACKEND_DIR, 'ota/version.json');
  const otaVersionDest = path.join(DIST_DIR, 'ota/version.json');
  if (fs.existsSync(otaVersionSrc)) {
    fse.ensureDirSync(path.dirname(otaVersionDest));
    fse.copyFileSync(otaVersionSrc, otaVersionDest);
  }
  // Copy data folder if exists
  const dataSrc = path.join(BACKEND_DIR, 'data');
  const dataDest = path.join(DIST_DIR, 'data');
  if (fs.existsSync(dataSrc)) {
    fse.copySync(dataSrc, dataDest, { overwrite: true });
  }
}

// Main build process
(async function build() {
  try {
    console.log('Cleaning dist folder...');
    cleanDist();
    console.log('Minifying frontend JS and CSS...');
    minifyFrontend();
    console.log('Copying frontend to backend/UI...');
    copyFrontendToBackendUI();
    console.log('Copying UI to dist/UI...');
    copyUIToDist();
    console.log('Copying Python files, wifi.dat, and ota/version.json to dist...');
    copyPythonToDist();
    console.log('Build complete. Files ready in Code/backend/dist.');
  } catch (err) {
    console.error('Build failed:', err);
    process.exit(1);
  }
})();
