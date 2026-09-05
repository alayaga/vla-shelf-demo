@echo off
cd /d "%~dp0"
npx --yes esbuild js/scene-bundle-entry.js --bundle --format=iife --outfile=js/scene-bundle.js --platform=browser --alias:three=./lib/three/three.module.js
echo scene-bundle.js rebuilt
