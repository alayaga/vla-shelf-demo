/** Resolve paths for both file:// and http:// */
window.Demo = window.Demo || {};
Demo.assetUrl = function assetUrl(relativePath) {
  return new URL(relativePath, window.location.href).href;
};

Demo.isFileProtocol = window.location.protocol === "file:";
