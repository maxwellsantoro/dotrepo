// Render untrusted profile values as text, with explicit scope and source gaps.
export function parseIdentity(raw) {
  let value = raw.trim();
  if (/^https?:\/\//i.test(value)) {
    const url = new URL(value);
    const hosted = url.pathname.match(/\/v0\/repos\/([^/]+)\/([^/]+)\/([^/]+)\/(?:profile|trust|index)\.json$/);
    value = hosted ? hosted.slice(1).join('/') : url.hostname + url.pathname;
  }
  let parts = value.replace(/^\/+|\/+$/g, '').replace(/\.git$/, '').split('/');
  if (parts.length === 2) parts.unshift('github.com');
  if (parts.length !== 3 || parts.some(p => !/^[a-z0-9][a-z0-9_.-]*$/i.test(p) || p === '.' || p === '..')) {
    throw new Error('Use owner/repo, host/owner/repo, or a repository URL.');
  }
  return {host:parts[0], owner:parts[1], repo:parts[2]};
}

export function profilePath(base, identity) {
  return base + '/v0/repos/' + [identity.host, identity.owner, identity.repo].map(encodeURIComponent).join('/') + '/profile.json';
}

export function safeLink(value) {
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : null; }
  catch { return null; }
}

export function evidenceURL(profile, source) {
  if (!source) return null;
  if (source.startsWith('https://')) return safeLink(source);
  if (profile.identity?.host !== 'github.com' || !/^[a-f0-9]{40}$/i.test(profile.record?.sourceRevision ?? '')) return null;
  const segments = source.split('/');
  if (segments.some(s => !/^[a-z0-9_.-]+$/i.test(s) || s === '..' || s === '.')) return null;
  return 'https://github.com/' + [profile.identity.owner, profile.identity.repo, 'blob', profile.record.sourceRevision, ...segments].map(encodeURIComponent).join('/');
}

export function contextDescription(command, context) {
  if (!context || context.command !== command) return 'Scope, working directory and prerequisites not retained for this value. Inspect upstream instructions.';
  const prerequisites = Array.isArray(context.prerequisites) ? context.prerequisites.join('; ') || 'explicitly none' : 'not retained';
  return `Scope: ${context.scope ?? 'unknown'}${context.component ? ' (' + context.component + ')' : ''}. Directory: ${context.workingDirectory ?? 'unknown'}. Prerequisites: ${prerequisites}.`;
}

export async function loadProfile(fetcher, path, expected) {
  const response = await fetcher(path, {redirect:'error'});
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Profile request failed (${response.status}). Try again or inspect upstream documentation.`);
  const profile = await response.json();
  if (!profile.identity || !profile.record) throw new Error('The profile response is incomplete. Inspect upstream documentation.');
  if (expected) {
    const insensitive = expected.host.toLowerCase() === 'github.com';
    const normalize = value => insensitive ? value.toLowerCase() : value;
    if (['host','owner','repo'].some(k => typeof profile.identity[k] !== 'string' || normalize(profile.identity[k]) !== normalize(expected[k]))) {
      throw new Error('The profile identity does not match the requested repository. Inspect upstream documentation.');
    }
  }
  return profile;
}

async function start() {
  const byId = id => document.getElementById(id);
  const base = document.querySelector('[data-site-base]').dataset.siteBase;
  const status = byId('repository-status');
  const input = byId('profile-repository');
  const raw = new URL(location.href).searchParams.get('repo');
  byId('profile-lookup').addEventListener('submit', event => {
    event.preventDefault();
    try {
      const id = parseIdentity(input.value);
      location.assign(base + '/repository/?repo=' + encodeURIComponent([id.host,id.owner,id.repo].join('/')));
    } catch(error) { status.textContent = error.message; input.focus(); }
  });
  if (!raw) return;
  input.value = raw;
  function text(tag, value, className) {
    const el = document.createElement(tag); el.textContent = value; if(className) el.className=className; return el;
  }
  function link(parent, value, label) {
    const href = value?.startsWith(base + '/') && !value.startsWith('//') ? value : safeLink(value);
    if (!href) return;
    const el = text('a',label); el.href=href; parent.append(el);
  }
  try {
    const identity = parseIdentity(raw);
    const label = [identity.host,identity.owner,identity.repo].join('/');
    byId('repository-title').textContent = label;
    status.textContent='Loading available facts…';
    link(byId('profile-links'),'https://' + identity.host + '/' + encodeURIComponent(identity.owner) + '/' + encodeURIComponent(identity.repo),'Upstream repository');
    const path=profilePath(base,identity);
    const profile=await loadProfile(fetch,path,identity);
    if (!profile) {
      status.textContent='No profile is available in this index.';
      byId('profile-missing').hidden=false;
      return;
    }
    byId('repository-title').textContent=profile.name || label;
    status.textContent=label + ' · ' + (profile.purpose || 'Project purpose not retained.');
    link(byId('profile-links'),path,'Profile JSON');
    link(byId('profile-links'),path.replace(/profile\.json$/,'trust.json'),'Trust JSON');
    link(byId('profile-links'),base+'/repositories/','Browse repositories');
    const trail=profile.record.evidencePath;
    if (typeof trail==='string' && trail.split('/').every(s=>/^[a-z0-9_.-]+$/i.test(s) && s!=='.' && s!=='..')) {
      link(byId('profile-links'),'https://github.com/maxwellsantoro/dotrepo/blob/main/index/'+trail.split('/').map(encodeURIComponent).join('/'),'Record evidence history');
    }
    function fact(target, title, value, assessment, context, source) {
      const card=text('article','', 'fact'); card.append(text('h3',title));
      card.append(text('p',value ?? 'Unknown — inspect upstream sources','fact-value'));
      if (safeLink(value)) link(card,value,'Open '+title.toLowerCase());
      if (context !== undefined && value) card.append(text('p',contextDescription(value,context),'fact-meta'));
      card.append(text('p',assessment
        ? `Assessment: ${assessment.state ?? 'unknown'} · confidence ${assessment.confidence ?? 'unknown'} · ${assessment.method ?? 'method unknown'}. Checked: ${assessment.checkedAt ?? 'unknown'}.`
        : 'No retained field assessment.','fact-meta'));
      if (assessment?.reason) card.append(text('p',assessment.reason,'fact-meta'));
      const actualSource=source || assessment?.source;
      if (actualSource) {
        card.append(text('p','Source: '+actualSource,'fact-meta'));
        link(card,evidenceURL(profile,actualSource),'Inspect source evidence');
      }
      target.append(card);
    }
    const e=profile.execution ?? {}, d=profile.docs ?? {}, o=profile.ownership ?? {}, a=profile.fieldEvidence ?? {};
    for (const [title,value,field,context] of [
      ['Purpose',profile.purpose,'repo.description'],
      ['Homepage',profile.homepage,'repo.homepage'],
      ['Build command',e.build,'repo.build',e.buildContext ?? null],
      ['Test command',e.test,'repo.test',e.testContext ?? null],
      ['Documentation',d.root,'docs.root'],
      ['Getting started',d.gettingStarted,'docs.getting_started'],
      ['Security reporting',o.securityContact,'owners.security_contact'],
      ['License',profile.license,'repo.license'],
    ]) fact(byId('profile-facts'),title,value,a[field],context);
    for (const [kind,candidates] of [['Build',e.buildCandidates],['Test',e.testCandidates]]) {
      for(const candidate of candidates ?? []) {
        byId('execution-candidates').hidden=false;
        fact(byId('candidate-facts'),kind+' candidate',candidate.command,null,candidate.context ?? null,candidate.source);
      }
    }
    const trust=profile.trust ?? {}, record=profile.record, freshness=profile.freshness ?? {};
    byId('profile-trust').textContent=`Selected record: ${trust.selectedStatus ?? 'unknown'}. Record confidence: ${trust.confidence ?? 'unknown'}. Provenance: ${(trust.provenance ?? []).join(', ') || 'unknown'}.`;
    const checked=Date.parse(record.generatedAt), now=Date.now();
    const age=Number.isFinite(checked) && checked<=now ? Math.floor((now-checked)/86400000)+' days old now' : 'age unknown';
    const agePolicy=typeof record.staleAfterDays==='number' && Number.isFinite(checked) && checked<=now
      ? ((now-checked)/86400000>record.staleAfterDays ? 'Record is stale; consult upstream.' : 'Within the record-age policy.')
      : 'Record-age policy cannot be evaluated.';
    const expired=Date.parse(freshness.staleAfter)<now;
    byId('profile-age').textContent=`Record generated: ${record.generatedAt ?? 'unknown'} (${age}). ${agePolicy} Snapshot exported: ${freshness.generatedAt ?? 'unknown'}. Snapshot revalidation due: ${freshness.staleAfter ?? 'unknown'}${expired ? ' — overdue; consult upstream' : ''}.`;
    const conflicts=profile.conflicts ?? [];
    byId('profile-conflicts').append(text('h3',conflicts.length ? 'Conflicting records — inspect before using these answers' : 'No conflicts reported'));
    if(conflicts.length) byId('profile-conflicts').append(text('pre',JSON.stringify(conflicts,null,2)));
    byId('profile-content').hidden=false;
    if(location.hash==='#trust') byId('trust').scrollIntoView();
  } catch(error) { status.textContent=error.message; }
}

if (typeof document !== 'undefined') start();
