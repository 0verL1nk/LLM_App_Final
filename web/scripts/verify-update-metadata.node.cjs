const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { verifyUpdateMetadata } = require("./verify-update-metadata.cjs");

function withReleaseDirectory(callback) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "papersage-update-metadata-"));
  try {
    callback(directory);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

test("accepts metadata whose installer is present in the release bundle", () => {
  withReleaseDirectory((directory) => {
    fs.writeFileSync(path.join(directory, "latest.yml"), "version: 1.3.2\npath: PaperSage-Setup-1.3.2.exe\n");
    fs.writeFileSync(path.join(directory, "PaperSage-Setup-1.3.2.exe"), "installer");

    assert.doesNotThrow(() => verifyUpdateMetadata(directory));
  });
});

test("rejects metadata whose installer is absent from the release bundle", () => {
  withReleaseDirectory((directory) => {
    fs.writeFileSync(path.join(directory, "latest.yml"), "version: 1.3.2\npath: PaperSage-Setup-1.3.2.exe\n");

    assert.throws(
      () => verifyUpdateMetadata(directory),
      /latest\.yml references missing artifact: PaperSage-Setup-1\.3\.2\.exe/,
    );
  });
});
