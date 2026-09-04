import { describe, expect, it } from "vitest";
import { BiomacConfigurationError, normalizeApiBaseUrl } from "./api-config";

describe("normalizeApiBaseUrl", () => {
  it("normalizes the trailing slash", () => {
    expect(normalizeApiBaseUrl("https://api.example.test/api/v2/")).toBe(
      "https://api.example.test/api/v2",
    );
  });

  it.each([undefined, "", "localhost:8001/api/v2", "ftp://api.test/api/v2", "https://api.test"])(
    "rejects absent or invalid configuration: %s",
    (value) => expect(() => normalizeApiBaseUrl(value)).toThrow(BiomacConfigurationError),
  );
});
