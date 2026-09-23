/* 华鑫医药工作台 —— 前端逻辑（原生 JS，无任何外部依赖） */
'use strict';

var FRAMEWORKS = [];
var POLLERS = {};      // runId -> intervalId
var RUN_OFFSETS = {};  // runId -> 已渲染的输出长度
var AUTO_REFRESH = null;
var WEIXIN = {};        // 微信槽位元信息（不含任何密钥）
var WECHAT_SETUP = '';  // setup_local_api.sh 相对路径

/* ---------------- 基础工具 ---------------- */

function $(id) { return document.getElementById(id); }

function esc(text) {
  return String(text == null ? '' : text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function api(path, options) {
  return fetch(path, options).then(function (res) {
    return res.text().then(function (text) {
      var data = {};
      if (text) { try { data = JSON.parse(text); } catch (e) { data = { error: text }; } }
      if (!res.ok) {
        var err = new Error(data.error || ('HTTP ' + res.status));
        err.payload = data;
        throw err;
      }
      return data;
    });
  });
}

function postJSON(path, body) {
  return api(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
}

function banner(kind, text) {
  var el = $('banner');
  if (!kind) { el.hidden = true; el.innerHTML = ''; return; }
  el.hidden = false;
  el.className = 'banner ' + (kind || '');
  el.innerHTML = text;
}

function statusBadge(el, status) {
  var s = status || '待配置';
  el.className = 'badge';
  if (s === '已连接') { el.className = 'badge ok'; }
  else if (s === '连接失败') { el.className = 'badge err'; }
  else if (s === '未配置' || s === '待配置') { el.className = 'badge warn'; }
  el.textContent = s;
}

/* ---------------- 框架卡片 ---------------- */

function renderFrameworks(payload) {
  FRAMEWORKS = payload.frameworks || [];

  var repoRoot = payload.repo_root || '—';
  $('repo-root').textContent = repoRoot;

  var dsh = payload.dsh || {};
  if (dsh.available) {
    $('dsh-meta').innerHTML = 'dsh <code>' + esc(dsh.version || '可用') + '</code> · profile <code>' +
      esc(dsh.profile || '') + '</code>';
  } else {
    $('dsh-meta').innerHTML = 'dsh <code>不可用</code>';
    banner('warn', '未能找到可用的 <code>dsh</code>：' + esc(dsh.message || '未知原因') +
      '。你仍可浏览框架与改配置，但「启动」会失败；请在下方「运行环境」里填写正确的 dsh 路径。');
  }

  var grid = $('fw-grid');
  grid.innerHTML = '';

  FRAMEWORKS.forEach(function (fw) {
    var card = document.createElement('div');
    card.className = 'fw';

    var desc = fw.skill_description
      ? '<div class="fw-hint">SKILL 描述：' + esc(fw.skill_description) + '</div>' : '';

    card.innerHTML =
      '<div class="fw-top">' +
        '<div>' +
          '<div class="fw-name">' + esc(fw.name) + '</div>' +
          '<div class="fw-path">' + esc(fw.skill) + '</div>' +
        '</div>' +
        '<span class="badge ' + (fw.exists ? 'ok' : 'err') + '">' +
          (fw.exists ? 'SKILL 就绪' : 'SKILL 缺失') + '</span>' +
      '</div>' +
      '<div class="fw-summary">' + esc(fw.summary) + '</div>' +
      desc +
      (fw.hint ? '<div class="fw-hint">' + esc(fw.hint) + '</div>' : '') +
      '<div class="fw-prompt-label"><span>提示词（可改）</span></div>' +
      '<textarea class="fw-prompt" data-prompt="' + esc(fw.key) + '">' + esc(fw.prompt) + '</textarea>' +
      '<div class="fw-actions">' +
        '<button class="primary" data-run="' + esc(fw.key) + '">启动</button>' +
        '<a class="link" href="/api/skill/' + encodeURIComponent(fw.key) +
          '" target="_blank" rel="noopener">查看 SKILL.md</a>' +
        '<span class="spacer" style="flex:1"></span>' +
      '</div>' +
      '<div class="fw-meta">' +
        '<span>' + esc(fw.dir) + '/</span><span class="dot">·</span>' +
        '<span>上次修改 ' + esc(fw.modified) + '</span>' +
      '</div>';

    grid.appendChild(card);
  });

  Array.prototype.forEach.call(grid.querySelectorAll('[data-run]'), function (btn) {
    btn.addEventListener('click', function () {
      startRun(btn.getAttribute('data-run'), btn);
    });
  });
}

/* ---------------- 启动运行 ---------------- */

function startRun(key, btn) {
  var box = document.querySelector('[data-prompt="' + key + '"]');
  var prompt = box ? box.value : '';
  var original = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> 启动中';

  postJSON('/api/run', { framework: key, prompt: prompt }).then(function (run) {
    btn.disabled = false;
    btn.textContent = original;
    if (run.error) { banner('err', esc(run.error)); }
    else { banner(null); }
    refreshRuns().then(function () {
      var el = document.querySelector('[data-run-head="' + run.id + '"]');
      if (el) { expandRun(run.id, true); }
      pollRun(run.id);
    });
  }).catch(function (err) {
    btn.disabled = false;
    btn.textContent = original;
    banner('err', '启动失败：' + esc(err.message));
  });
}

/* ---------------- 运行列表 ---------------- */

function runBadge(status) {
  if (status === 'running') { return '<span class="badge run">运行中</span>'; }
  if (status === 'succeeded') { return '<span class="badge ok">成功</span>'; }
  if (status === 'failed') { return '<span class="badge err">失败</span>'; }
  return '<span class="badge">' + esc(status) + '</span>';
}

function refreshRuns() {
  return api('/api/runs').then(function (data) {
    var runs = data.runs || [];
    var list = $('run-list');
    if (!runs.length) {
      list.innerHTML = '<div class="empty">暂无运行记录。</div>';
      return;
    }
    list.innerHTML = '';

    runs.forEach(function (run) {
      var node = document.createElement('div');
      node.className = 'run';
      node.setAttribute('data-run-node', run.id);

      var code = run.exit_code === null || run.exit_code === undefined
        ? '—' : run.exit_code;

      node.innerHTML =
        '<div class="run-head" data-run-head="' + esc(run.id) + '">' +
          '<span class="caret">▶</span>' +
          '<span class="name">' + esc(run.framework_name) + '</span>' +
          runBadge(run.status) +
          '<span class="id">' + esc(run.id) + '</span>' +
          '<span class="spacer"></span>' +
          '<span class="time">退出码 ' + esc(code) + '</span>' +
          '<span class="time">' + esc(run.started_at) + '</span>' +
        '</div>' +
        '<div class="run-body">' +
          (run.error ? '<div class="run-err">' + esc(run.error) + '</div>' : '') +
          '<div class="run-cmd"><span class="k">$</span> ' +
            esc((run.command || []).join(' ')) + '</div>' +
          '<pre class="run-out" data-run-out="' + esc(run.id) + '"></pre>' +
        '</div>';

      node.querySelector('[data-run-head]').addEventListener('click', function () {
        expandRun(run.id);
      });
      list.appendChild(node);

      if (run.status === 'running') { pollRun(run.id); }
    });
  }).catch(function (err) {
    banner('err', '无法读取运行列表：' + esc(err.message));
  });
}

function expandRun(runId, force) {
  var node = document.querySelector('[data-run-node="' + runId + '"]');
  if (!node) { return; }
  var open = node.classList.contains('open');
  if (force) { node.classList.add('open'); }
  else { node.classList.toggle('open'); }
  if (!open || force) {
    if (RUN_OFFSETS[runId] === undefined) { RUN_OFFSETS[runId] = 0; }
    fetchRunChunk(runId);
  }
}

/* ---------------- 轮询单次运行 ---------------- */

function fetchRunChunk(runId) {
  var offset = RUN_OFFSETS[runId] || 0;
  return api('/api/runs/' + encodeURIComponent(runId) + '?offset=' + offset)
    .then(function (run) {
      var out = document.querySelector('[data-run-out="' + runId + '"]');
      if (out && run.output) {
        out.textContent += run.output;
        out.scrollTop = out.scrollHeight;
      }
      RUN_OFFSETS[runId] = run.next_offset || 0;

      var node = document.querySelector('[data-run-node="' + runId + '"]');
      if (node) {
        var head = node.querySelector('.run-head');
        var badge = head.querySelector('.badge');
        var tmp = document.createElement('div');
        tmp.innerHTML = runBadge(run.status);
        head.replaceChild(tmp.firstChild, badge);
        var times = head.querySelectorAll('.time');
        if (times.length) {
          times[0].textContent = '退出码 ' +
            (run.exit_code === null || run.exit_code === undefined ? '—' : run.exit_code);
        }
        var errBox = node.querySelector('.run-err');
        if (run.error && !errBox) {
          var div = document.createElement('div');
          div.className = 'run-err';
          div.textContent = run.error;
          node.querySelector('.run-body').insertBefore(div, node.querySelector('.run-cmd'));
        }
      }

      if (run.status !== 'running') {
        stopPoll(runId);
        if (run.error) { banner('err', esc(run.error)); }
      }
      return run;
    })
    .catch(function () { stopPoll(runId); });
}

function pollRun(runId) {
  if (POLLERS[runId]) { return; }
  POLLERS[runId] = setInterval(function () { fetchRunChunk(runId); }, 1200);
}

function stopPoll(runId) {
  if (POLLERS[runId]) { clearInterval(POLLERS[runId]); delete POLLERS[runId]; }
}

/* ---------------- 配置 ---------------- */

function fillConfig(cfg) {
  var ds = cfg.deepseek || {};
  $('ds-base').value = ds.base_url || '';
  $('ds-key').value = ds.api_key || '';
  $('ds-model').value = ds.model || '';
  statusBadge($('badge-deepseek'), (cfg.status || {}).deepseek);
  if ((cfg.status || {}).deepseek_message) {
    showMsg('ds-msg', (cfg.status || {}).deepseek_message,
      (cfg.status || {}).deepseek === '已连接' ? 'ok' : 'err');
  }

  var wc = cfg.wechat || {};
  WEIXIN = wc;
  statusBadge($('badge-wechat'), wc.status);
  if (wc.status_message) {
    showMsg('wc-msg', wc.status_message, wc.status === '已连接' ? 'ok' : 'err');
  }
  if (wc.setup_script) { WECHAT_SETUP = wc.setup_script; }

  var dsh = cfg.dsh || {};
  $('dsh-command').value = dsh.command || '';
  $('dsh-profile').value = dsh.profile || '';
}

function showMsg(id, text, kind) {
  var el = $(id);
  el.hidden = false;
  el.className = 'cfg-msg ' + (kind || '');
  el.textContent = text;
}

function loadConfig() {
  return api('/api/config').then(fillConfig).catch(function (err) {
    banner('err', '无法读取配置：' + esc(err.message));
  });
}

function configPayload() {
  // 只提交 DeepSeek：微信凭证不走 config.json，也不经网页表单。
  return {
    deepseek: {
      base_url: $('ds-base').value.trim(),
      api_key: $('ds-key').value,
      model: $('ds-model').value.trim()
    }
  };
}

function saveConfig(btn, msgId, extra) {
  var label = btn.textContent;
  btn.disabled = true;
  var payload = configPayload();
  if (extra) { Object.keys(extra).forEach(function (k) { payload[k] = extra[k]; }); }

  return postJSON('/api/config', payload).then(function (cfg) {
    fillConfig(cfg);
    showMsg(msgId, '已保存到 workbench/config.json', 'ok');
    return cfg;
  }).catch(function (err) {
    showMsg(msgId, '保存失败：' + err.message, 'err');
  }).then(function (r) {
    btn.disabled = false;
    btn.textContent = label;
    return r;
  });
}

/* ---------------- 微信公众号（只复用既成凭证机制） ---------------- */

function wechatCheck(btn) {
  var label = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spin"></span> 检查中'; }
  showMsg('wc-msg', '正在运行 check-auth（最长 45 秒）…', '');

  return postJSON('/api/wechat/check', {}).then(function (res) {
    statusBadge($('badge-wechat'), res.status);
    var text = res.status_message || res.message || '';
    if (res.errcode) { text += '\n微信返回：errcode=' + res.errcode + ' errmsg=' + res.errmsg; }
    if (res.output && res.status !== '已连接') { text += '\n\n' + res.output; }
    showMsg('wc-msg', text, res.status === '已连接' ? 'ok' : 'err');
    return res;
  }).catch(function (err) {
    statusBadge($('badge-wechat'), '连接失败');
    showMsg('wc-msg', '检查失败：' + err.message, 'err');
  }).then(function (r) {
    if (btn) { btn.disabled = false; btn.innerHTML = label; }
    return r;
  });
}

function wechatConfigure(btn) {
  var label = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> 正在打开终端';

  postJSON('/api/wechat/configure', {}).then(function (res) {
    showMsg('wc-msg', res.message, 'ok');
    // 给用户时间去终端里填写，然后自动复查一次状态。
    var tries = 0;
    var timer = setInterval(function () {
      tries += 1;
      if (tries > 10) { clearInterval(timer); return; }
      api('/api/wechat/status').then(function (s) {
        statusBadge($('badge-wechat'), s.status);
      });
    }, 6000);
  }).catch(function (err) {
    var payload = err.payload || {};
    showMsg('wc-msg', payload.message || ('无法打开终端：' + err.message), 'err');
  }).then(function () {
    btn.disabled = false;
    btn.textContent = label;
  });
}

/* ---------------- 事件绑定 ---------------- */

function bind() {
  $('ds-save').addEventListener('click', function () {
    saveConfig(this, 'ds-msg', null).then(refreshFrameworks);
  });

  $('ds-clear').addEventListener('click', function () {
    if (!confirm('确定清空已保存的 DeepSeek api_key？清空后需要重新填写才能调用模型。')) { return; }
    var btn = this;
    var label = btn.textContent;
    btn.disabled = true;
    btn.textContent = '清除中…';
    postJSON('/api/config', {
      deepseek: { clear_api_key: true }
    }).then(function (cfg) {
      fillConfig(cfg);
      $('ds-key').value = '';
      showMsg('ds-msg', '已清空已保存的 api_key', 'ok');
      return refreshFrameworks();
    }).catch(function (err) {
      showMsg('ds-msg', '清除失败：' + err.message, 'err');
    }).then(function () {
      btn.disabled = false;
      btn.textContent = label;
    });
  });

  $('ds-test').addEventListener('click', function () {
    var btn = this;
    btn.disabled = true;
    showMsg('ds-msg', '正在请求 /v1/models …', '');    postJSON('/api/test-deepseek', {
      deepseek: {
        base_url: $('ds-base').value.trim(),
        api_key: $('ds-key').value,
        model: $('ds-model').value.trim()
      }
    }).then(function (res) {
      statusBadge($('badge-deepseek'), res.status);
      var text = res.message || '';
      if (res.ok && (res.models || []).length) {
        text += '\n可用模型：' + res.models.slice(0, 12).join('、') +
          (res.models.length > 12 ? ' …' : '');
      }
      if (res.endpoint) { text += '\n端点：' + res.endpoint; }
      showMsg('ds-msg', text, res.ok ? 'ok' : 'err');
      return loadConfig();
    }).catch(function (err) {
      showMsg('ds-msg', '测试失败：' + err.message, 'err');
      statusBadge($('badge-deepseek'), '连接失败');
    }).then(function () {
      btn.disabled = false;
      btn.textContent = '测试连接';
    });
  });

  $('wc-configure').addEventListener('click', function () { wechatConfigure(this); });

  $('wc-test').addEventListener('click', function () { wechatCheck(this); });

  $('dsh-save').addEventListener('click', function () {
    var btn = this;
    btn.disabled = true;
    postJSON('/api/config', {
      dsh: {
        command: $('dsh-command').value.trim(),
        profile: $('dsh-profile').value.trim()
      }
    }).then(function (cfg) {
      fillConfig(cfg);
      showMsg('dsh-msg', '已保存。', 'ok');
      return refreshFrameworks();
    }).catch(function (err) {
      showMsg('dsh-msg', '保存失败：' + err.message, 'err');
    }).then(function () {
      btn.disabled = false;
      btn.textContent = '保存';
    });
  });

  $('dsh-recheck').addEventListener('click', function () {
    var btn = this;
    btn.disabled = true;
    api('/api/dsh').then(function (info) {
      var lines = [
        '可用：' + (info.available ? '是' : '否'),
        '解析路径：' + (info.resolved || '（无）'),
        '版本：' + (info.version || '未知'),
        'DSH_HOME：' + (info.dsh_home || '未知'),
        '可用 profile：' + ((info.profiles || []).join('、') || '（读取不到）')
      ];
      if (info.message) { lines.push('说明：' + info.message); }
      showMsg('dsh-msg', lines.join('\n'), info.available ? 'ok' : 'err');
      return refreshFrameworks();
    }).catch(function (err) {
      showMsg('dsh-msg', '探测失败：' + err.message, 'err');
    }).then(function () {
      btn.disabled = false;
      btn.textContent = '重新探测';
    });
  });

  $('runs-refresh').addEventListener('click', function () { refreshRuns(); });

  $('runs-auto').addEventListener('click', function () {
    if (AUTO_REFRESH) {
      clearInterval(AUTO_REFRESH); AUTO_REFRESH = null;
      this.textContent = '自动刷新：关';
    } else {
      AUTO_REFRESH = setInterval(refreshRuns, 5000);
      this.textContent = '自动刷新：开';
    }
  });
}

function refreshFrameworks() {
  return api('/api/frameworks').then(renderFrameworks).catch(function (err) {
    banner('err', '无法读取框架列表：' + esc(err.message));
  });
}

/* ---------------- 启动 ---------------- */

function boot() {
  $('svc-url').textContent = window.location.origin;
  bind();
  loadConfig().then(function () {
    // 配置读完后跑一次真实 check-auth，让状态徽章如实反映本机情况。
    wechatCheck(null);
  });
  refreshFrameworks();
  refreshRuns();
  AUTO_REFRESH = setInterval(refreshRuns, 5000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
