import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dataDir = path.join(__dirname, 'data');
const dataFile = path.join(dataDir, 'todos.json');
const publicDir = path.join(__dirname, 'public');
const PORT = process.env.PORT || 3000;
const DEFAULT_USER_ID = 'demo-user';

fs.mkdirSync(dataDir, { recursive: true });

function loadTodos() {
  if (!fs.existsSync(dataFile)) return [];
  try {
    const raw = fs.readFileSync(dataFile, 'utf8');
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveTodos(todos) {
  fs.writeFileSync(dataFile, JSON.stringify(todos, null, 2));
}

let todos = loadTodos();

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,PATCH,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  });
  res.end(JSON.stringify(payload));
}

function sendText(res, statusCode, contentType, body) {
  res.writeHead(statusCode, { 'Content-Type': contentType });
  res.end(body);
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      if (!body) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(error);
      }
    });
    req.on('error', reject);
  });
}

function now() {
  return new Date().toISOString();
}

function makeId() {
  return `todo_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function serializeTodo(todo) {
  return {
    id: todo.id,
    user_id: todo.user_id,
    title: todo.title,
    description: todo.description,
    status: todo.status,
    priority: todo.priority,
    due_at: todo.due_at,
    completed_at: todo.completed_at,
    created_at: todo.created_at,
    updated_at: todo.updated_at
  };
}

function validatePriority(priority) {
  return [undefined, null, '', 'low', 'medium', 'high'].includes(priority);
}

function validateStatus(status) {
  return ['pending', 'completed'].includes(status);
}

function getVisibleTodos() {
  return todos.filter((todo) => todo.user_id === DEFAULT_USER_ID && !todo.deleted_at);
}

function sortItems(items, sortBy = 'created_at', order = 'desc') {
  const dir = order === 'asc' ? 1 : -1;
  const allowed = new Set(['created_at', 'updated_at', 'due_at']);
  const key = allowed.has(sortBy) ? sortBy : 'created_at';
  return [...items].sort((a, b) => {
    const av = a[key] || '';
    const bv = b[key] || '';
    if (av === bv) return 0;
    return av > bv ? dir : -dir;
  });
}

function serveStatic(req, res, pathname) {
  const target = pathname === '/' ? '/index.html' : pathname;
  const filePath = path.join(publicDir, target);
  if (!filePath.startsWith(publicDir) || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    sendText(res, 404, 'text/plain; charset=utf-8', 'Not Found');
    return;
  }
  const ext = path.extname(filePath);
  const types = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8'
  };
  sendText(res, 200, types[ext] || 'application/octet-stream', fs.readFileSync(filePath));
}

async function handleApi(req, res, pathname, urlObj) {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,PATCH,DELETE,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    });
    return res.end();
  }

  if (pathname === '/api/v1/todos' && req.method === 'POST') {
    try {
      const body = await parseBody(req);
      if (!body.title || !String(body.title).trim()) {
        return sendJson(res, 400, { code: 400, message: 'title is required', data: null });
      }
      if (!validatePriority(body.priority)) {
        return sendJson(res, 400, { code: 400, message: 'invalid priority', data: null });
      }
      const timestamp = now();
      const todo = {
        id: makeId(),
        user_id: DEFAULT_USER_ID,
        title: String(body.title).trim(),
        description: body.description ? String(body.description).trim() : '',
        status: 'pending',
        priority: body.priority || 'medium',
        due_at: body.due_at || null,
        completed_at: null,
        created_at: timestamp,
        updated_at: timestamp,
        deleted_at: null
      };
      todos.unshift(todo);
      saveTodos(todos);
      return sendJson(res, 201, { code: 0, message: 'success', data: serializeTodo(todo) });
    } catch {
      return sendJson(res, 400, { code: 400, message: 'invalid json body', data: null });
    }
  }

  if (pathname === '/api/v1/todos' && req.method === 'GET') {
    const params = urlObj.searchParams;
    const status = params.get('status');
    const priority = params.get('priority');
    const keyword = (params.get('keyword') || '').trim().toLowerCase();
    const sortBy = params.get('sort_by') || 'created_at';
    const order = params.get('order') || 'desc';
    const page = Math.max(Number(params.get('page') || '1'), 1);
    const pageSize = Math.min(Math.max(Number(params.get('page_size') || '20'), 1), 100);

    let items = getVisibleTodos();
    if (status && validateStatus(status)) items = items.filter((todo) => todo.status === status);
    if (priority && ['low', 'medium', 'high'].includes(priority)) items = items.filter((todo) => todo.priority === priority);
    if (keyword) {
      items = items.filter((todo) =>
        todo.title.toLowerCase().includes(keyword) || todo.description.toLowerCase().includes(keyword)
      );
    }
    items = sortItems(items, sortBy, order);
    const total = items.length;
    const paged = items.slice((page - 1) * pageSize, page * pageSize).map(serializeTodo);
    return sendJson(res, 200, {
      code: 0,
      message: 'success',
      data: {
        items: paged,
        pagination: { page, page_size: pageSize, total }
      }
    });
  }

  const statusMatch = pathname.match(/^\/api\/v1\/todos\/([^/]+)\/status$/);
  if (statusMatch && req.method === 'PATCH') {
    try {
      const body = await parseBody(req);
      if (!validateStatus(body.status)) {
        return sendJson(res, 400, { code: 400, message: 'invalid status', data: null });
      }
      const todo = todos.find((item) => item.id === statusMatch[1] && item.user_id === DEFAULT_USER_ID && !item.deleted_at);
      if (!todo) return sendJson(res, 404, { code: 404, message: 'todo not found', data: null });
      todo.status = body.status;
      todo.completed_at = body.status === 'completed' ? now() : null;
      todo.updated_at = now();
      saveTodos(todos);
      return sendJson(res, 200, { code: 0, message: 'success', data: serializeTodo(todo) });
    } catch {
      return sendJson(res, 400, { code: 400, message: 'invalid json body', data: null });
    }
  }

  const todoMatch = pathname.match(/^\/api\/v1\/todos\/([^/]+)$/);
  if (todoMatch && req.method === 'GET') {
    const todo = todos.find((item) => item.id === todoMatch[1] && item.user_id === DEFAULT_USER_ID && !item.deleted_at);
    if (!todo) return sendJson(res, 404, { code: 404, message: 'todo not found', data: null });
    return sendJson(res, 200, { code: 0, message: 'success', data: serializeTodo(todo) });
  }

  if (todoMatch && req.method === 'PATCH') {
    try {
      const body = await parseBody(req);
      const todo = todos.find((item) => item.id === todoMatch[1] && item.user_id === DEFAULT_USER_ID && !item.deleted_at);
      if (!todo) return sendJson(res, 404, { code: 404, message: 'todo not found', data: null });
      if (body.title !== undefined) {
        if (!String(body.title).trim()) {
          return sendJson(res, 400, { code: 400, message: 'title is required', data: null });
        }
        todo.title = String(body.title).trim();
      }
      if (body.description !== undefined) todo.description = String(body.description || '').trim();
      if (body.priority !== undefined) {
        if (!validatePriority(body.priority)) {
          return sendJson(res, 400, { code: 400, message: 'invalid priority', data: null });
        }
        todo.priority = body.priority || 'medium';
      }
      if (body.due_at !== undefined) todo.due_at = body.due_at || null;
      todo.updated_at = now();
      saveTodos(todos);
      return sendJson(res, 200, { code: 0, message: 'success', data: serializeTodo(todo) });
    } catch {
      return sendJson(res, 400, { code: 400, message: 'invalid json body', data: null });
    }
  }

  if (todoMatch && req.method === 'DELETE') {
    const todo = todos.find((item) => item.id === todoMatch[1] && item.user_id === DEFAULT_USER_ID && !item.deleted_at);
    if (!todo) return sendJson(res, 404, { code: 404, message: 'todo not found', data: null });
    todo.deleted_at = now();
    todo.updated_at = now();
    saveTodos(todos);
    return sendJson(res, 200, { code: 0, message: 'success', data: true });
  }

  return sendJson(res, 404, { code: 404, message: 'not found', data: null });
}

const server = http.createServer(async (req, res) => {
  const urlObj = new URL(req.url, `http://${req.headers.host}`);
  if (urlObj.pathname.startsWith('/api/')) {
    return handleApi(req, res, urlObj.pathname, urlObj);
  }
  return serveStatic(req, res, urlObj.pathname);
});

server.listen(PORT, () => {
  console.log(`Todo app running at http://localhost:${PORT}`);
});
