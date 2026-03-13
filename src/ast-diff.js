import * as acorn from 'acorn';
import crypto from 'crypto';
import jsBeautify from 'js-beautify';
const { js_beautify } = jsBeautify;
import { diffLines } from 'diff';

const MAX_AST_SIZE = 2 * 1024 * 1024; // 2MB default

/**
 * Parse JS source into an AST. Tries module mode first, falls back to script.
 */
function parseSource(source) {
  const opts = { ecmaVersion: 'latest', sourceType: 'module', locations: true };
  try {
    return acorn.parse(source, opts);
  } catch {
    try {
      return acorn.parse(source, { ...opts, sourceType: 'script' });
    } catch {
      return null;
    }
  }
}

/**
 * Hash a string with MD5.
 */
function hash(str) {
  return crypto.createHash('md5').update(str).digest('hex');
}

/**
 * Extract a symbol table from AST top-level body nodes.
 * Returns Map<name, { name, kind, start, end, sourceSlice, hash, line }>
 */
function extractSymbols(ast, source) {
  const symbols = new Map();
  let body = ast.body;

  // IIFE unwrapping: if single ExpressionStatement wrapping a call to a function expression
  if (body.length === 1 && body[0].type === 'ExpressionStatement') {
    const expr = body[0].expression;
    if (expr.type === 'CallExpression' &&
        (expr.callee.type === 'FunctionExpression' || expr.callee.type === 'ArrowFunctionExpression') &&
        expr.callee.body.type === 'BlockStatement') {
      body = expr.callee.body.body;
    }
  }

  for (const node of body) {
    const entries = extractFromNode(node, source);
    for (const entry of entries) {
      symbols.set(entry.name, entry);
    }
  }

  return symbols;
}

function extractFromNode(node, source) {
  const slice = source.slice(node.start, node.end);
  const line = node.loc?.start?.line ?? 0;

  switch (node.type) {
    case 'FunctionDeclaration':
      if (node.id) {
        return [{ name: node.id.name, kind: 'function', start: node.start, end: node.end, sourceSlice: slice, hash: hash(slice), line }];
      }
      return [];

    case 'ClassDeclaration':
      if (node.id) {
        return [{ name: node.id.name, kind: 'class', start: node.start, end: node.end, sourceSlice: slice, hash: hash(slice), line }];
      }
      return [];

    case 'VariableDeclaration': {
      const results = [];
      for (const decl of node.declarators || node.declarations || []) {
        if (decl.id && decl.id.name) {
          const declSlice = source.slice(decl.start, decl.end);
          results.push({
            name: decl.id.name,
            kind: 'variable',
            start: decl.start,
            end: decl.end,
            sourceSlice: declSlice,
            hash: hash(declSlice),
            line: decl.loc?.start?.line ?? line,
          });
        }
      }
      return results;
    }

    case 'ImportDeclaration':
      return [{ name: `import:${node.source.value}`, kind: 'import', start: node.start, end: node.end, sourceSlice: slice, hash: hash(slice), line }];

    case 'ExportNamedDeclaration':
      if (node.declaration) {
        const inner = extractFromNode(node.declaration, source);
        return inner.map(s => ({ ...s, kind: `export:${s.kind}` }));
      }
      return [{ name: `export:named:${node.start}`, kind: 'export', start: node.start, end: node.end, sourceSlice: slice, hash: hash(slice), line }];

    case 'ExportDefaultDeclaration':
      return [{ name: 'export:default', kind: 'export:default', start: node.start, end: node.end, sourceSlice: slice, hash: hash(slice), line }];

    case 'ExpressionStatement': {
      // Handle things like: initApp(); or module.exports = ...
      const expr = node.expression;
      if (expr.type === 'CallExpression' && expr.callee.type === 'Identifier') {
        return [{ name: `call:${expr.callee.name}`, kind: 'call', start: node.start, end: node.end, sourceSlice: slice, hash: hash(slice), line }];
      }
      if (expr.type === 'AssignmentExpression' && expr.left.type === 'MemberExpression') {
        const leftSrc = source.slice(expr.left.start, expr.left.end);
        return [{ name: `assign:${leftSrc}`, kind: 'assignment', start: node.start, end: node.end, sourceSlice: slice, hash: hash(slice), line }];
      }
      return [];
    }

    default:
      return [];
  }
}

/**
 * Generate a scoped diff for a modified symbol.
 */
function scopedDiff(oldSlice, newSlice) {
  const oldBeautified = js_beautify(oldSlice);
  const newBeautified = js_beautify(newSlice);
  const changes = diffLines(oldBeautified, newBeautified);

  const lines = [];
  for (const part of changes) {
    const partLines = part.value.split('\n').filter(l => l !== '');
    if (part.added) {
      for (const l of partLines) lines.push(`+${l}`);
    } else if (part.removed) {
      for (const l of partLines) lines.push(`-${l}`);
    } else {
      for (const l of partLines) lines.push(` ${l}`);
    }
  }
  return lines.join('\n');
}

/**
 * Perform AST-based diff between old and new JS content.
 * Returns { success, summary, changes[], fallbackReason? }
 *
 * Each change: { type: 'added'|'removed'|'modified', kind, name, line, source?, diff? }
 */
export function astDiff(oldSource, newSource, options = {}) {
  const { maxAstSize = MAX_AST_SIZE } = options;

  // Size check
  if (oldSource.length > maxAstSize || newSource.length > maxAstSize) {
    return { success: false, fallbackReason: `File exceeds max AST size (${maxAstSize} bytes)` };
  }

  const oldAst = parseSource(oldSource);
  const newAst = parseSource(newSource);

  if (!oldAst || !newAst) {
    return { success: false, fallbackReason: 'Failed to parse JavaScript (falling back to text diff)' };
  }

  const oldSymbols = extractSymbols(oldAst, oldSource);
  const newSymbols = extractSymbols(newAst, newSource);

  const oldKeys = new Set(oldSymbols.keys());
  const newKeys = new Set(newSymbols.keys());

  const added = [...newKeys].filter(k => !oldKeys.has(k));
  const removed = [...oldKeys].filter(k => !newKeys.has(k));
  const modified = [...oldKeys].filter(k => newKeys.has(k) && oldSymbols.get(k).hash !== newSymbols.get(k).hash);

  const changes = [];

  // Counts by kind for summary
  const summaryCounts = { added: {}, removed: {}, modified: {} };

  for (const name of added) {
    const sym = newSymbols.get(name);
    const kind = sym.kind.replace('export:', '');
    summaryCounts.added[kind] = (summaryCounts.added[kind] || 0) + 1;
    changes.push({
      type: 'added',
      kind: sym.kind,
      name,
      line: sym.line,
      source: js_beautify(sym.sourceSlice),
    });
  }

  for (const name of removed) {
    const sym = oldSymbols.get(name);
    const kind = sym.kind.replace('export:', '');
    summaryCounts.removed[kind] = (summaryCounts.removed[kind] || 0) + 1;
    changes.push({
      type: 'removed',
      kind: sym.kind,
      name,
      line: sym.line,
      source: js_beautify(sym.sourceSlice),
    });
  }

  for (const name of modified) {
    const oldSym = oldSymbols.get(name);
    const newSym = newSymbols.get(name);
    const kind = newSym.kind.replace('export:', '');
    summaryCounts.modified[kind] = (summaryCounts.modified[kind] || 0) + 1;
    changes.push({
      type: 'modified',
      kind: newSym.kind,
      name,
      line: newSym.line,
      diff: scopedDiff(oldSym.sourceSlice, newSym.sourceSlice),
    });
  }

  // Build summary lines
  const summaryLines = [];
  for (const [kind, count] of Object.entries(summaryCounts.modified)) {
    summaryLines.push(`${count} ${kind}${count > 1 ? 's' : ''} modified`);
  }
  for (const [kind, count] of Object.entries(summaryCounts.added)) {
    summaryLines.push(`${count} ${kind}${count > 1 ? 's' : ''} added`);
  }
  for (const [kind, count] of Object.entries(summaryCounts.removed)) {
    summaryLines.push(`${count} ${kind}${count > 1 ? 's' : ''} removed`);
  }

  return {
    success: true,
    summary: summaryLines,
    changes,
  };
}
