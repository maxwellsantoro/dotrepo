import test from 'node:test';
import assert from 'node:assert/strict';
import {parseIdentity, profilePath, safeLink, evidenceURL, contextDescription, loadProfile} from '../../../scripts/public_repository.mjs';

test('repository inputs stay in the local API namespace', () => {
  for (const input of ['astral-sh/uv','github.com/astral-sh/uv','https://github.com/astral-sh/uv.git','https://dotrepo.org/v0/repos/github.com/astral-sh/uv/profile.json']) {
    assert.equal(profilePath('/prefix',parseIdentity(input)),'/prefix/v0/repos/github.com/astral-sh/uv/profile.json');
  }
  for (const input of ['../uv','github.com/a/..','a/b/c/d','a/%2fattack','javascript:alert(1)','']) {
    assert.throws(() => parseIdentity(input));
  }
});

test('source links require safe HTTPS or a pinned GitHub file', () => {
  const p={identity:parseIdentity('astral-sh/uv'),record:{sourceRevision:'a'.repeat(40)}};
  assert.equal(evidenceURL(p,'CONTRIBUTING.md'),'https://github.com/astral-sh/uv/blob/'+ 'a'.repeat(40) +'/CONTRIBUTING.md');
  for (const source of ['../escape','GitHub API','javascript:alert(1)']) assert.equal(evidenceURL(p,source),null);
  assert.equal(evidenceURL({...p,record:{}},'README.md'),null);
  assert.equal(safeLink('javascript:alert(1)'),null);
  assert.equal(safeLink('https://user:secret@example.com'),null);
});

test('context is shown only for the command it describes', () => {
  const context={command:'make test',scope:'component',component:'api',workingDirectory:'api',prerequisites:['make setup']};
  assert.match(contextDescription('make test',context),/component \(api\).*Directory: api.*make setup/);
  assert.match(contextDescription('cargo test',context),/not retained/);
  assert.match(contextDescription('make test',null),/not retained/);
});

test('a miss, transport error, and mismatched identity remain distinct', async () => {
  assert.equal(await loadProfile(async()=>new Response('',{status:404}),'/profile'),null);
  await assert.rejects(loadProfile(async()=>new Response('',{status:503}),'/profile'),/503/);
  const expected=parseIdentity('astral-sh/uv');
  await assert.rejects(loadProfile(async()=>Response.json({identity:parseIdentity('other/project'),record:{}}),'/profile',expected),/does not match/);
  const p={identity:expected,record:{}};
  assert.deepEqual(await loadProfile(async()=>Response.json(p),'/profile',expected),p);
});
