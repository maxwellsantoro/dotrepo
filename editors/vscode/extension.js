'use strict';

const path = require('path');
const cp = require('child_process');
const vscode = require('vscode');
const { LanguageClient } = require('vscode-languageclient/node');

let client;
let outputChannel;

function activate(context) {
  outputChannel = vscode.window.createOutputChannel('dotrepo');
  context.subscriptions.push(outputChannel);

  client = createLanguageClient();
  context.subscriptions.push(client.start());

  context.subscriptions.push(
    vscode.commands.registerCommand('dotrepo.validateCurrentManifest', () =>
      runCliCommand('validate', ['validate'])
    ),
    vscode.commands.registerCommand('dotrepo.trustCurrentManifest', () =>
      runCliCommand('trust', ['trust'])
    ),
    vscode.commands.registerCommand('dotrepo.doctorCurrentManifest', () =>
      runCliCommand('doctor', ['doctor'])
    ),
    vscode.commands.registerCommand('dotrepo.generateCheckCurrentManifest', () =>
      runCliCommand('generate --check', ['generate', '--check'])
    )
  );
}

function deactivate() {
  if (!client) {
    return undefined;
  }
  return client.stop();
}

function createLanguageClient() {
  const configuration = vscode.workspace.getConfiguration('dotrepo');
  const command = configuration.get('languageServer.command', 'dotrepo-lsp');
  const args = configuration.get('languageServer.args', []);

  const serverOptions = {
    run: { command, args },
    debug: { command, args }
  };

  const clientOptions = {
    documentSelector: [
      { scheme: 'file', language: 'dotrepo' },
      { scheme: 'file', language: 'dotrepo-overlay' }
    ],
    outputChannel,
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher('**/{.repo,record.toml}')
    }
  };

  return new LanguageClient(
    'dotrepo',
    'dotrepo Language Server',
    serverOptions,
    clientOptions
  );
}

async function runCliCommand(label, subcommandArgs) {
  let root;
  try {
    root = resolveDotrepoRoot();
  } catch (error) {
    vscode.window.showErrorMessage(String(error.message || error));
    return;
  }

  const configuration = vscode.workspace.getConfiguration('dotrepo');
  const command = configuration.get('cli.command', 'dotrepo');
  const args = configuration.get('cli.args', []);
  const invocation = [...args, '--root', root, ...subcommandArgs];

  outputChannel.show(true);
  outputChannel.appendLine(`$ ${formatCommand(command, invocation)}`);

  try {
    const result = await execFile(command, invocation, { cwd: root });
    if (result.stdout.trim()) {
      outputChannel.appendLine(result.stdout.trimEnd());
    }
    if (result.stderr.trim()) {
      outputChannel.appendLine(result.stderr.trimEnd());
    }
    vscode.window.setStatusBarMessage(`dotrepo ${label} succeeded`, 3000);
  } catch (error) {
    if (error.stdout && error.stdout.trim()) {
      outputChannel.appendLine(error.stdout.trimEnd());
    }
    if (error.stderr && error.stderr.trim()) {
      outputChannel.appendLine(error.stderr.trimEnd());
    }
    const message = error.code === 'ENOENT'
      ? `Failed to run ${command}. Configure dotrepo.languageServer.command / dotrepo.cli.command or add dotrepo binaries to PATH.`
      : `dotrepo ${label} failed`;
    const action = await vscode.window.showErrorMessage(message, 'Show Output');
    if (action === 'Show Output') {
      outputChannel.show(true);
    }
  }
}

function resolveDotrepoRoot() {
  const editor = vscode.window.activeTextEditor;
  if (editor && isManifestDocument(editor.document)) {
    return path.dirname(editor.document.uri.fsPath);
  }

  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  if (folder) {
    return folder.uri.fsPath;
  }

  throw new Error('Open a .repo or record.toml file, or open a workspace containing one.');
}

function isManifestDocument(document) {
  const basename = path.basename(document.uri.fsPath);
  return basename === '.repo' || basename === 'record.toml';
}

function execFile(command, args, options) {
  return new Promise((resolve, reject) => {
    cp.execFile(command, args, options, (error, stdout, stderr) => {
      if (error) {
        error.stdout = stdout || '';
        error.stderr = stderr || '';
        reject(error);
        return;
      }
      resolve({ stdout: stdout || '', stderr: stderr || '' });
    });
  });
}

function formatCommand(command, args) {
  return [command, ...args.map(shellQuote)].join(' ');
}

function shellQuote(value) {
  return /\s/.test(value) ? JSON.stringify(value) : value;
}

module.exports = {
  activate,
  deactivate
};
