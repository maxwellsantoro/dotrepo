'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function loadExtension(start = async () => {}) {
  const subscriptions = [];
  const commands = [];
  const channel = { dispose() {}, info() {}, error() {}, warn() {}, debug() {} };
  let client;
  let channelOptions;
  const vscode = {
    window: {
      createOutputChannel(name, options) {
        assert.equal(name, 'dotrepo');
        channelOptions = options;
        return channel;
      }
    },
    workspace: {
      getConfiguration() { return { get(_key, fallback) { return fallback; } }; },
      createFileSystemWatcher() { return { dispose() {} }; }
    },
    commands: {
      registerCommand(name) {
        commands.push(name);
        return { dispose() {} };
      }
    }
  };
  class LanguageClient {
    constructor(_id, _name, _serverOptions, options) {
      this.options = options;
      this.stopped = false;
      client = this;
    }
    start() { return start(); }
    async stop() { this.stopped = true; }
    dispose() {}
  }
  const sandbox = {
    module: { exports: {} },
    require(name) {
      if (name === 'vscode') return vscode;
      if (name === 'vscode-languageclient/node') return { LanguageClient };
      return require(name);
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'extension.js'), 'utf8'), sandbox);
  return {
    extension: sandbox.module.exports,
    context: { subscriptions },
    commands,
    channel,
    get client() { return client; },
    get channelOptions() { return channelOptions; }
  };
}

test('activation uses a log output channel and only registers disposables', async () => {
  const loaded = loadExtension();
  await loaded.extension.activate(loaded.context);
  assert.equal(loaded.channelOptions.log, true);
  assert.equal(loaded.client.options.outputChannel, loaded.channel);
  assert.equal(loaded.commands.length, 4);
  assert.ok(loaded.context.subscriptions.includes(loaded.client));
  assert.ok(loaded.context.subscriptions.every(value => typeof value.dispose === 'function'));
  await loaded.extension.deactivate();
  assert.equal(loaded.client.stopped, true);
});

test('activation waits for startup and propagates startup failures', async () => {
  let finish;
  const loaded = loadExtension(() => new Promise(resolve => { finish = resolve; }));
  let activated = false;
  const activation = loaded.extension.activate(loaded.context).then(() => { activated = true; });
  await Promise.resolve();
  assert.equal(activated, false);
  finish();
  await activation;
  assert.equal(activated, true);

  const failure = new Error('server failed to start');
  const broken = loadExtension(async () => { throw failure; });
  await assert.rejects(broken.extension.activate(broken.context), error => error === failure);
});

test('deactivation is safe before activation', () => {
  assert.equal(loadExtension().extension.deactivate(), undefined);
});

test('extension and lockfile agree with the language client minimum VS Code engine', () => {
  const pkg = require('./package.json');
  const lock = require('./package-lock.json');
  const clientEngine = lock.packages['node_modules/vscode-languageclient'].engines.vscode;
  assert.equal(pkg.engines.vscode, clientEngine);
  assert.equal(lock.packages[''].engines.vscode, pkg.engines.vscode);
});
