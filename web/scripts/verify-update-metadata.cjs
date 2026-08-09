const fs = require("node:fs");
const path = require("node:path");

const METADATA_FILE_PATTERN = /^latest(?:-(?:mac|linux))?\.yml$/;

function artifactPathFromMetadata(metadata) {
  const match = metadata.match(/^path:\s*["']?([^\r\n"']+)["']?\s*$/m);
  if (!match) {
    throw new Error("Updater metadata does not declare a top-level path.");
  }
  return match[1].trim();
}

function verifyUpdateMetadata(releaseDirectory) {
  const metadataFiles = fs.readdirSync(releaseDirectory)
    .filter((name) => METADATA_FILE_PATTERN.test(name));

  if (metadataFiles.length === 0) {
    throw new Error(`No updater metadata found in ${releaseDirectory}.`);
  }

  for (const metadataFile of metadataFiles) {
    const metadataPath = path.join(releaseDirectory, metadataFile);
    const artifactPath = artifactPathFromMetadata(fs.readFileSync(metadataPath, "utf8"));
    const resolvedArtifact = path.resolve(releaseDirectory, artifactPath);
    const relativeArtifact = path.relative(releaseDirectory, resolvedArtifact);
    if (relativeArtifact.startsWith("..") || path.isAbsolute(relativeArtifact)) {
      throw new Error(`${metadataFile} references an artifact outside the release directory: ${artifactPath}`);
    }
    if (!fs.existsSync(resolvedArtifact)) {
      throw new Error(`${metadataFile} references missing artifact: ${artifactPath}`);
    }
  }
}

if (require.main === module) {
  verifyUpdateMetadata(path.resolve(__dirname, "..", "release"));
}

module.exports = { artifactPathFromMetadata, verifyUpdateMetadata };
