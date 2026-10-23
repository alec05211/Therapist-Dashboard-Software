#!/usr/bin/env node

import { randomBytes } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const REPOSITORY_ROOT = path.resolve(import.meta.dirname, "..");
const DEFAULT_CONNECTION = "Username-Password-Authentication";
const DEFAULT_CREDENTIAL_OUTPUT = path.join(
  REPOSITORY_ROOT,
  ".secrets",
  "auth0-synthetic-users.json",
);

const fixtureRoots = [
  path.join(REPOSITORY_ROOT, "demo-data", "Clients"),
  path.join(REPOSITORY_ROOT, "demo-data", "Therapists"),
];

function parseArguments(argv) {
  const options = {
    apply: false,
    connection: process.env.AUTH0_SYNTHETIC_CONNECTION || DEFAULT_CONNECTION,
    credentialOutput: DEFAULT_CREDENTIAL_OUTPUT,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--apply") {
      options.apply = true;
    } else if (argument === "--connection") {
      options.connection = argv[++index];
    } else if (argument === "--credential-output") {
      options.credentialOutput = path.resolve(argv[++index]);
    } else if (argument === "--help" || argument === "-h") {
      options.help = true;
    } else {
      throw new Error(`Unknown argument: ${argument}`);
    }
  }

  if (!options.connection) {
    throw new Error("--connection requires a value");
  }

  return options;
}

function printHelp() {
  console.log(`Usage:
  node tools/provision_auth0_synthetic_users.mjs
  node --env-file=<credential-file> tools/provision_auth0_synthetic_users.mjs --apply

Options:
  --apply                       Create missing users. Without this flag, only validates fixtures.
  --connection <name>           Auth0 database connection (default: ${DEFAULT_CONNECTION}).
  --credential-output <path>    Ignored JSON file for generated sign-in credentials.

Required environment variables for --apply:
  AUTH0_DOMAIN
  AUTH0_CLIENT_ID
  AUTH0_CLIENT_SECRET
`);
}

async function findAccountProfiles(root) {
  const entries = await import("node:fs/promises").then(({ readdir }) =>
    readdir(root, { withFileTypes: true }),
  );
  return entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(root, entry.name, "account-profile.json"));
}

async function loadFixtures() {
  const profilePaths = (
    await Promise.all(fixtureRoots.map((root) => findAccountProfiles(root)))
  ).flat();

  const fixtures = [];
  for (const profilePath of profilePaths) {
    let profile;
    try {
      profile = JSON.parse(await readFile(profilePath, "utf8"));
    } catch (error) {
      if (error?.code === "ENOENT") continue;
      throw new Error(`Unable to read ${profilePath}: ${error.message}`);
    }

    if (profile.fictional !== true) {
      throw new Error(`Refusing non-fictional account fixture: ${profilePath}`);
    }
    if (!['client', 'therapist'].includes(profile.role)) {
      throw new Error(`Unsupported fixture role in ${profilePath}`);
    }
    if (typeof profile.email !== "string" || !profile.email.endsWith("@example.com")) {
      throw new Error(`Fixture email must use example.com: ${profilePath}`);
    }
    if (typeof profile.display_name !== "string" || !profile.display_name.trim()) {
      throw new Error(`Fixture display_name is required: ${profilePath}`);
    }

    fixtures.push({
      email: profile.email.toLowerCase(),
      name: profile.display_name,
      role: profile.role,
      fixturePath: path.relative(REPOSITORY_ROOT, profilePath),
    });
  }

  fixtures.sort((left, right) => left.email.localeCompare(right.email));
  const duplicates = fixtures.filter(
    (fixture, index) => index > 0 && fixture.email === fixtures[index - 1].email,
  );
  if (duplicates.length > 0) {
    throw new Error(`Duplicate fixture email: ${duplicates[0].email}`);
  }
  return fixtures;
}

function normalizeDomain(value) {
  return value.replace(/^https?:\/\//, "").replace(/\/$/, "");
}

function requireProvisionerEnvironment() {
  const required = ["AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET"];
  const missing = required.filter((key) => !process.env[key]);
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(", ")}`);
  }
  return {
    domain: normalizeDomain(process.env.AUTH0_DOMAIN),
    clientId: process.env.AUTH0_CLIENT_ID,
    clientSecret: process.env.AUTH0_CLIENT_SECRET,
  };
}

async function responseJson(response, operation) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body.message || body.error_description || body.error || response.statusText;
    throw new Error(`${operation} failed (${response.status}): ${message}`);
  }
  return body;
}

async function getManagementToken(configuration) {
  const response = await fetch(`https://${configuration.domain}/oauth/token`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      grant_type: "client_credentials",
      client_id: configuration.clientId,
      client_secret: configuration.clientSecret,
      audience: `https://${configuration.domain}/api/v2/`,
    }),
  });
  const body = await responseJson(response, "Management API token request");
  return body.access_token;
}

async function findUserByEmail(domain, token, email) {
  const url = new URL(`https://${domain}/api/v2/users-by-email`);
  url.searchParams.set("email", email);
  const response = await fetch(url, {
    headers: { authorization: `Bearer ${token}` },
  });
  return responseJson(response, `User lookup for ${email}`);
}

function generatePassword() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*";
  const required = ["A", "a", "7", "!"];
  const random = randomBytes(28);
  const characters = required.concat(
    Array.from(random, (byte) => alphabet[byte % alphabet.length]),
  );

  for (let index = characters.length - 1; index > 0; index -= 1) {
    const swapIndex = randomBytes(1)[0] % (index + 1);
    [characters[index], characters[swapIndex]] = [characters[swapIndex], characters[index]];
  }
  return characters.join("");
}

async function createUser(domain, token, connection, fixture, password) {
  const response = await fetch(`https://${domain}/api/v2/users`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      connection,
      email: fixture.email,
      name: fixture.name,
      password,
      email_verified: true,
      verify_email: false,
      user_metadata: {
        display_name: fixture.name,
      },
      app_metadata: {
        synthetic_fixture: true,
        fixture_role: fixture.role,
        fixture_source: fixture.fixturePath.replaceAll("\\", "/"),
      },
    }),
  });
  return responseJson(response, `Create user ${fixture.email}`);
}

async function readCredentialManifest(outputPath) {
  try {
    const document = JSON.parse(await readFile(outputPath, "utf8"));
    return Array.isArray(document.users) ? document.users : [];
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw new Error(`Unable to read the existing credential manifest: ${error.message}`);
  }
}

async function writeCredentialManifest(outputPath, records) {
  await mkdir(path.dirname(outputPath), { recursive: true });
  const existingRecords = await readCredentialManifest(outputPath);
  const recordsByEmail = new Map(
    existingRecords.map((record) => [record.email?.toLowerCase(), record]),
  );
  for (const record of records) {
    recordsByEmail.set(record.email.toLowerCase(), record);
  }
  const document = {
    generated_at: new Date().toISOString(),
    warning: "Synthetic development credentials. Keep this file out of source control.",
    users: [...recordsByEmail.values()].sort((left, right) =>
      left.email.localeCompare(right.email),
    ),
  };
  await writeFile(outputPath, `${JSON.stringify(document, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }

  const fixtures = await loadFixtures();
  const clientCount = fixtures.filter((fixture) => fixture.role === "client").length;
  const therapistCount = fixtures.filter((fixture) => fixture.role === "therapist").length;
  console.log(
    `Validated ${fixtures.length} fictional account fixtures: ${clientCount} clients, ${therapistCount} therapists.`,
  );

  if (!options.apply) {
    for (const fixture of fixtures) {
      console.log(`DRY RUN  ${fixture.role.padEnd(9)} ${fixture.email}`);
    }
    console.log("No Auth0 requests were made. Re-run with --apply to provision missing users.");
    return;
  }

  const configuration = requireProvisionerEnvironment();
  const token = await getManagementToken(configuration);
  const credentials = [];
  let createdCount = 0;
  let skippedCount = 0;

  for (const fixture of fixtures) {
    const matches = await findUserByEmail(configuration.domain, token, fixture.email);
    if (matches.length > 0) {
      skippedCount += 1;
      console.log(`SKIPPED  ${fixture.email} already exists`);
      continue;
    }

    const password = generatePassword();
    const user = await createUser(
      configuration.domain,
      token,
      options.connection,
      fixture,
      password,
    );
    credentials.push({
      email: fixture.email,
      password,
      role: fixture.role,
      auth0_subject: user.user_id,
    });
    createdCount += 1;
    console.log(`CREATED  ${fixture.email}`);
  }

  if (credentials.length > 0) {
    await writeCredentialManifest(options.credentialOutput, credentials);
    console.log(`Saved ${credentials.length} generated sign-in credential records to an ignored local file.`);
  }
  console.log(`Provisioning complete: ${createdCount} created, ${skippedCount} skipped.`);
}

main().catch((error) => {
  console.error(`Provisioning failed: ${error.message}`);
  process.exitCode = 1;
});
