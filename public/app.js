const listEl = document.getElementById('todo-list');
const messageEl = document.getElementById('message');
const summaryEl = document.getElementById('summary');
const template = document.getElementById('todo-item-template');
const createForm = document.getElementById('create-form');
const editDialog = document.getElementById('edit-dialog');
const editForm = document.getElementById('edit-form');

const filters = {
  status: document.getElementById('filter-status'),
  priority: document.getElementById('filter-priority'),
  keyword: document.getElementById('filter-keyword'),
  sortBy: document.getElementById('sort-by'),
  sortOrder: document.getElementById('sort-order')
};

function setMessage(text, isError = false) {
  messageEl.textContent = text;
  messageEl.style.color = isError ? '#b42318' : '#475467';
}

function localToIso(value) {
  if (!value) return null;
  return new Date(value).toISOString();
}

function isoToLocal(value) {
  if (!value) return '';
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60000);
  return local.toISOString().slice(0, 16);
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  });
  const result = await response.json();
  if (!response.ok || result.code !== 0) {
    throw new Error(result.message || 'request failed');
  }
  return result.data;
}

function renderMeta(todo) {
  const parts = [
    `状态：${todo.status === 'completed' ? '已完成' : '未完成'}`,
    `创建：${new Date(todo.created_at).toLocaleString()}`,
    `更新：${new Date(todo.updated_at).toLocaleString()}`
  ];
  if (todo.due_at) parts.push(`截止：${new Date(todo.due_at).toLocaleString()}`);
  return parts.join(' · ');
}

function renderList(items, total) {
  listEl.innerHTML = '';
  summaryEl.textContent = `共 ${total} 项`;
  if (!items.length) {
    listEl.innerHTML = '<div class="card"><p>暂无符合条件的任务。</p></div>';
    return;
  }

  items.forEach((todo) => {
    const node = template.content.firstElementChild.cloneNode(true);
    node.dataset.id = todo.id;
    node.classList.toggle('completed', todo.status === 'completed');

    const title = node.querySelector('.todo-title');
    title.textContent = todo.title;
    title.classList.toggle('completed', todo.status === 'completed');

    const checkbox = node.querySelector('.toggle-status');
    checkbox.checked = todo.status === 'completed';
    checkbox.addEventListener('change', () => toggleStatus(todo, checkbox.checked));

    const description = node.querySelector('.todo-description');
    description.textContent = todo.description || '暂无描述';

    const priority = node.querySelector('.priority');
    priority.textContent = `优先级：${{ low: '低', medium: '中', high: '高' }[todo.priority] || '中'}`;
    priority.className = `badge priority priority-${todo.priority || 'medium'}`;

    node.querySelector('.meta').textContent = renderMeta(todo);
    node.querySelector('.delete-btn').addEventListener('click', () => removeTodo(todo.id));
    node.querySelector('.edit-btn').addEventListener('click', () => openEdit(todo));
    listEl.appendChild(node);
  });
}

async function fetchTodos() {
  const params = new URLSearchParams();
  if (filters.status.value) params.set('status', filters.status.value);
  if (filters.priority.value) params.set('priority', filters.priority.value);
  if (filters.keyword.value.trim()) params.set('keyword', filters.keyword.value.trim());
  params.set('sort_by', filters.sortBy.value);
  params.set('order', filters.sortOrder.value);

  try {
    setMessage('加载中...');
    const data = await request(`/api/v1/todos?${params.toString()}`);
    renderList(data.items, data.pagination.total);
    setMessage('');
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function createTodo(event) {
  event.preventDefault();
  const formData = new FormData(createForm);
  const payload = Object.fromEntries(formData.entries());
  payload.due_at = localToIso(payload.due_at);
  try {
    await request('/api/v1/todos', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    createForm.reset();
    createForm.priority.value = 'medium';
    setMessage('任务已创建');
    await fetchTodos();
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function toggleStatus(todo, checked) {
  try {
    await request(`/api/v1/todos/${todo.id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: checked ? 'completed' : 'pending' })
    });
    setMessage('状态已更新');
    await fetchTodos();
  } catch (error) {
    setMessage(error.message, true);
    await fetchTodos();
  }
}

async function removeTodo(id) {
  if (!window.confirm('确认删除这个任务吗？')) return;
  try {
    await request(`/api/v1/todos/${id}`, { method: 'DELETE' });
    setMessage('任务已删除');
    await fetchTodos();
  } catch (error) {
    setMessage(error.message, true);
  }
}

function openEdit(todo) {
  editForm.id.value = todo.id;
  editForm.title.value = todo.title;
  editForm.description.value = todo.description || '';
  editForm.priority.value = todo.priority || 'medium';
  editForm.due_at.value = isoToLocal(todo.due_at);
  editDialog.showModal();
}

async function saveEdit(event) {
  event.preventDefault();
  const formData = new FormData(editForm);
  const payload = Object.fromEntries(formData.entries());
  const id = payload.id;
  delete payload.id;
  payload.due_at = localToIso(payload.due_at);
  try {
    await request(`/api/v1/todos/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
    editDialog.close();
    setMessage('任务已更新');
    await fetchTodos();
  } catch (error) {
    setMessage(error.message, true);
  }
}

createForm.addEventListener('submit', createTodo);
editForm.addEventListener('submit', saveEdit);
document.getElementById('cancel-edit').addEventListener('click', () => editDialog.close());
Object.values(filters).forEach((element) => {
  element.addEventListener('change', fetchTodos);
  if (element.tagName === 'INPUT') {
    let timer;
    element.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(fetchTodos, 180);
    });
  }
});

fetchTodos();
