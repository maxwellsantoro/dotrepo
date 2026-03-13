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
      runCliCommand('doctor', ['doctor'], { requiresNativeManifest: true })
    ),
    vscode.commands.registerCommand('dotrepo.generateCheckCurrentManifest', () =>
      runCliCommand('generate --check', ['generate', '--check'], { requiresNativeManifest: true })
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

async function runCliCommand(label, subcommandArgs, options = {}) {
  let context;
  try {
    context = resolveDotrepoContext();
  } catch (error) {
    vscode.window.showErrorMessage(String(error.message || error));
    return;
  }

  if (options.requiresNativeManifest && context.mode === 'overlay') {
    const message = `dotrepo ${label} is only supported for native .repo manifests.`;
    outputChannel.show(true);
    outputChannel.appendLine(message);
    vscode.window.showErrorMessage(message);
    return;
  }

  const configuration = vscode.workspace.getConfiguration('dotrepo');
  const command = configuration.get('cli.command', 'dotrepo');
  const args = configuration.get('cli.args', []);
  const invocation = [...args, '--root', context.root, ...subcommandArgs];

  outputChannel.show(true);
  outputChannel.appendLine(`$ ${formatCommand(command, invocation)}`);

  try {
    const result = await execFile(command, invocation, { cwd: context.root });
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

function resolveDotrepoContext() {
  const editor = vscode.window.activeTextEditor;
  if (editor) {
    const context = manifestContextFromDocument(editor.document);
    if (context) {
      return context;
    }

    if (isDotrepoNamedDocument(editor.document)) {
      throw new Error('dotrepo overlay manifests must live under repos/<host>/<owner>/<repo>/record.toml.');
    }
  }

  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  if (folder) {
    return { root: folder.uri.fsPath, mode: 'workspace' };
  }

  throw new Error('Open a .repo file, an overlay record under repos/<host>/<owner>/<repo>/record.toml, or a workspace containing one.');
}

function manifestContextFromDocument(document) {
  const basename = path.basename(document.uri.fsPath);
  if (basename === '.repo') {
    return { root: path.dirname(document.uri.fsPath), mode: 'native' };
  }
  if (basename === 'record.toml' && isOverlayManifestPath(document.uri.fsPath)) {
    return { root: path.dirname(document.uri.fsPath), mode: 'overlay' };
  }
  return null;
}

function isDotrepoNamedDocument(document) {
  const basename = path.basename(document.uri.fsPath);
  return basename === '.repo' || basename === 'record.toml';
}

function isOverlayManifestPath(fsPath) {
  const normalized = fsPath.split(path.sep).join('/');
  return /(?:^|\/)repos\/[^/]+\/[^/]+\/[^/]+\/record\.toml$/.test(normalized);
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
