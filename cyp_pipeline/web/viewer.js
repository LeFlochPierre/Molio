/* Two independent coordinate views. No predicted contacts or synthetic geometry. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const average = points => [0, 1, 2].map(i => points.reduce((sum, p) => sum + p[i], 0) / Math.max(points.length, 1));
  const distance = (a, b) => Math.hypot(...a.map((n, i) => n - b[i]));
  const validPoint = point => Array.isArray(point) && point.length === 3 && point.every(Number.isFinite);
  let renderers = [];
  try {
    const data = JSON.parse($('sentinelData').textContent);
    let references = data.structures, structures = references, preparedPayload = null;
    let referenceKeys = Object.keys(references), requestedTarget = data.target.id;
    let key = references[requestedTarget] ? requestedTarget : referenceKeys[0], comparisonKey = null;
    let pocket = false, rotating = false;
    function catmull(a, b, c, d, t) {
      return [0, 1, 2].map(i => .5 * ((2 * b[i]) + (-a[i] + c[i]) * t + (2 * a[i] - 5 * b[i] + 4 * c[i] - d[i]) * t * t + (-a[i] + 3 * b[i] - 3 * c[i] + d[i]) * t * t * t));
    }
    class CoordinateView {
      constructor(ids) {
        this.canvas = $(ids.canvas); this.stage = $(ids.stage); this.title = $(ids.title);
        this.chip = $(ids.chip); this.note = $(ids.note); this.error = $(ids.error);
        this.fallback = ids.fallback ? $(ids.fallback) : null;
        this.ctx = this.canvas.getContext('2d');
        if (!this.ctx) throw Error('Canvas rendering unavailable');
        this.width = 1; this.height = 1; this.rx = -.28; this.ry = .5; this.zoom = 1;
        this.dragging = false; this.frame = null; this.last = 0; this.structure = null;
        this.installControls();
        if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => this.resize()).observe(this.stage);
      }
      load(structure, id) {
        this.structure = structure;
        this.canvas.hidden = !structure;
        if (this.fallback && !structure) this.fallback.hidden = true;
        this.error.hidden = Boolean(structure);
        if (!structure) {
          this.title.textContent = id === 'custom' ? 'New protein' : id || 'No comparison';
          this.chip.textContent = 'No reference loaded';
          this.note.textContent = 'A sequence is not a 3D structure. Build prediction inputs first.';
          this.error.textContent = 'No structure available for this target yet.';
          this.canvas.removeAttribute('data-rendered');
          return;
        }
        const name = structure.protein_id || id;
        this.title.textContent = name;
        const label = document.createElement('span');
        label.textContent = structure.prepared ? (structure.uploaded ? 'uploaded prepared pocket' : 'prepared candidate pocket') : 'reference structure';
        this.title.append(label);
        this.chip.textContent = structure.prepared ? `${structure.atoms.length} heavy atoms · supplied coordinates` : `${structure.pdb} · chain ${structure.chain}`;
        this.note.textContent = structure.prepared
          ? `${structure.ligand_label} · ${structure.uploaded ? 'uploaded coordinates' : 'prepared coordinates'} · not a new pose prediction.`
          : `${structure.pdb} · ${structure.ligand_label} reference complex; not a predicted pose for the selected candidate.`;
        const chain = structure.backbone || [];
        this.trace = [];
        for (let i = 0; i < chain.length - 1; i++) {
          if (distance(chain[i], chain[i + 1]) > 4.8) continue;
          const a = i > 0 && distance(chain[i - 1], chain[i]) < 4.8 ? chain[i - 1] : chain[i];
          const d = i + 2 < chain.length && distance(chain[i + 1], chain[i + 2]) < 4.8 ? chain[i + 2] : chain[i + 1];
          let before = chain[i];
          for (let n = 1; n <= 6; n++) {
            const after = catmull(a, chain[i], chain[i + 1], d, n / 6);
            this.trace.push([before, after, i / chain.length]); before = after;
          }
        }
        // These distances create display sticks, not chemical bond assignments.
        this.bonds = [];
        for (let i = 0; i < structure.atoms.length; i++) for (let j = 0; j < i; j++) {
          const a = structure.atoms[i], b = structure.atoms[j], length = distance(a.p, b.p);
          if (a.group === b.group && length < 1.9 && length > .35) this.bonds.push([i, j]);
        }
        this.fit(); this.resize(); this.schedule();
      }
      fit() {
        if (!this.structure) return;
        const atoms = this.structure.atoms.map(a => a.p);
        const points = pocket || !this.structure.backbone?.length ? atoms : this.structure.backbone;
        this.center = pocket && validPoint(this.structure.center) ? this.structure.center : average(points);
        this.radius = Math.max(1, ...points.map(p => distance(p, this.center)));
        this.zoom = 1;
      }
      project(point) {
        const [x, y, z] = point.map((n, i) => n - this.center[i]);
        const xx = x * Math.cos(this.ry) + z * Math.sin(this.ry), zz = -x * Math.sin(this.ry) + z * Math.cos(this.ry);
        const yy = y * Math.cos(this.rx) - zz * Math.sin(this.rx), depth = y * Math.sin(this.rx) + zz * Math.cos(this.rx);
        const scale = Math.min(this.width * .43, this.height * .39) / this.radius * this.zoom;
        return [this.width * .5 + xx * scale, this.height * .50 + yy * scale, depth];
      }
      segment(a, b, color, size) {
        const ctx = this.ctx; ctx.strokeStyle = color; ctx.lineWidth = size; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      }
      sphere(point, color, size) {
        const ctx = this.ctx;
        ctx.fillStyle = color; ctx.beginPath(); ctx.arc(point[0], point[1], size, 0, Math.PI * 2); ctx.fill();
        if (size > 2) {ctx.fillStyle = '#ffffff77'; ctx.beginPath(); ctx.arc(point[0] - size * .25, point[1] - size * .3, size * .24, 0, Math.PI * 2); ctx.fill();}
      }
      render(time = 0) {
        this.frame = null;
        const structure = this.structure;
        if (!structure || this.stage.getBoundingClientRect().width < 1) return;
        if (rotating && !this.dragging && !document.hidden) this.ry += Math.min(40, time - this.last) * .00015;
        this.last = time;
        const ctx = this.ctx; ctx.clearRect(0, 0, this.width, this.height);
        const elements = [];
        if (!pocket) for (const [a, b, t] of this.trace) {
          const pa = this.project(a), pb = this.project(b), depth = (pa[2] + pb[2]) / 2;
          const light = 50 + (depth / this.radius + 1) * 12;
          elements.push({z: depth, draw: () => this.segment(pa, pb, `hsl(${205 + t * 20} 36% ${light}%)`, Math.max(1.9, 3.15 * this.zoom))});
        }
        const positions = structure.atoms.map(a => this.project(a.p));
        const show = atom => pocket || structure.prepared || !['pocket', 'axial'].includes(atom.group);
        for (const [i, j] of this.bonds) {
          const atom = structure.atoms[i]; if (!show(atom)) continue;
          const color = atom.group === 'ligand' ? '#299b89' : atom.group === 'heme' ? '#cba05c' : '#a0b5ce';
          const size = atom.group === 'ligand' ? 2.9 : atom.group === 'heme' ? 2.1 : 1.25;
          elements.push({z: (positions[i][2] + positions[j][2]) / 2, draw: () => this.segment(positions[i], positions[j], color, size * Math.sqrt(this.zoom))});
        }
        structure.atoms.forEach((atom, i) => {
          if (!show(atom)) return;
          const color = atom.e === 'FE' ? '#b27b34' : atom.group === 'ligand' ? '#229d89' : atom.group === 'heme' ? '#d7ac63' : '#8eacc8';
          const base = atom.e === 'FE' ? 5 : atom.group === 'ligand' ? 3.5 : atom.group === 'heme' ? 2.5 : 1.8;
          elements.push({z: positions[i][2], draw: () => this.sphere(positions[i], color, Math.max(1, base * (pocket || structure.prepared ? 1 : .7) * Math.sqrt(this.zoom)))});
        });
        elements.sort((a, b) => a.z - b.z).forEach(e => e.draw());
        if (pocket || structure.prepared) {
          const guides = structure.guides || (structure.iron && structure.donor ? [{a: structure.iron, b: structure.donor}] : []);
          guides.forEach((guide, index) => {
            if (!validPoint(guide.a) || !validPoint(guide.b)) return;
            const a = this.project(guide.a), b = this.project(guide.b);
            ctx.setLineDash([3, 4]); this.segment(a, b, '#98825b', 1); ctx.setLineDash([]);
            const label = `${distance(guide.a, guide.b).toFixed(2)} Å`;
            ctx.font = '9px system-ui';
            const x = Math.max(8, Math.min(this.width - 58, (a[0] + b[0]) / 2 + 10));
            const y = Math.max(30, Math.min(this.height - 16, (a[1] + b[1]) / 2 - 6 + index * 12));
            ctx.fillStyle = '#ffffffdf'; ctx.fillRect(x - 4, y - 10, ctx.measureText(label).width + 8, 14);
            ctx.fillStyle = '#9a835f'; ctx.fillText(label, x, y);
          });
        }
        this.canvas.classList.add('ready'); this.canvas.dataset.rendered = 'true';
        this.canvas.dataset.structure = structure.protein_id || structure.pdb || '';
        if (this.fallback) this.fallback.hidden = true;
        if (rotating && !document.hidden) this.schedule();
      }
      schedule() {if (this.frame === null) this.frame = requestAnimationFrame(time => this.render(time));}
      resize() {
        const bounds = this.stage.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
        this.width = Math.max(1, bounds.width); this.height = Math.max(1, bounds.height);
        this.canvas.width = Math.round(this.width * dpr); this.canvas.height = Math.round(this.height * dpr);
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0); this.schedule();
      }
      reset() {this.rx = -.28; this.ry = .5; this.fit(); this.schedule();}
      installControls() {
        let pointer = null;
        this.canvas.addEventListener('pointerdown', event => {this.dragging = true; pointer = [event.clientX, event.clientY]; this.canvas.setPointerCapture(event.pointerId);});
        this.canvas.addEventListener('pointermove', event => {
          if (!this.dragging) return;
          this.ry += (event.clientX - pointer[0]) * .009; this.rx += (event.clientY - pointer[1]) * .009;
          pointer = [event.clientX, event.clientY]; this.schedule();
        });
        ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(name => this.canvas.addEventListener(name, () => {this.dragging = false;}));
        this.canvas.addEventListener('wheel', event => {event.preventDefault(); this.zoom = Math.max(.5, Math.min(3.5, this.zoom * Math.exp(-event.deltaY * .001))); this.schedule();}, {passive: false});
        this.canvas.addEventListener('keydown', event => {
          if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '+', '=', '-'].includes(event.key)) return;
          event.preventDefault();
          if (event.key === 'ArrowLeft') this.ry -= .15; if (event.key === 'ArrowRight') this.ry += .15;
          if (event.key === 'ArrowUp') this.rx -= .15; if (event.key === 'ArrowDown') this.rx += .15;
          if (event.key === '+' || event.key === '=') this.zoom = Math.min(3.5, this.zoom * 1.12);
          if (event.key === '-') this.zoom = Math.max(.5, this.zoom / 1.12);
          this.schedule();
        });
      }
    }
    const mainView = new CoordinateView({canvas: 'molecule', stage: 'moleculeStage', title: 'proteinTitle', chip: 'viewChip', note: 'structureNote', error: 'viewerError', fallback: 'structureFallback'});
    const compareView = new CoordinateView({canvas: 'compareMolecule', stage: 'compareStage', title: 'compareProteinTitle', chip: 'compareViewChip', note: 'compareNote', error: 'compareError'});
    renderers = [mainView, compareView];
    const proteinName = id => structures[id]?.protein_id || id;
    function refreshComparison() {
      const available = Object.keys(structures).filter(id => id !== key);
      if (!available.includes(comparisonKey)) {
        const preferred = proteinName(key) === 'CYP11B2' ? 'CYP11B1' : 'CYP11B2';
        comparisonKey = available.find(id => proteinName(id) === preferred) || available[0] || null;
      }
      const visible = Boolean(structures[key] && comparisonKey);
      $('comparePane').hidden = !visible; $('viewerGrid').classList.toggle('single', !visible);
      $('compareTarget').replaceChildren();
      available.forEach(id => {const option = document.createElement('option'); option.value = id; option.textContent = proteinName(id); $('compareTarget').append(option);});
      $('compareTarget').value = comparisonKey || '';
      $('compareTarget').hidden = available.length < 2;
      if (visible) compareView.load(structures[comparisonKey], comparisonKey);
      else compareView.load(null, null);
      $('primaryRole').textContent = proteinName(key) === requestedTarget ? 'TARGET' : 'SELECTED PROTEIN';
      $('compareRole').textContent = proteinName(comparisonKey) === requestedTarget ? 'TARGET' : preparedPayload?.origin === 'prepared-pair' ? 'COUNTER-TARGET' : 'COMPARISON';
      requestAnimationFrame(() => renderers.forEach(view => view.resize()));
    }
    function loadStructure() {
      mainView.load(structures[key], key); refreshComparison();
      document.querySelectorAll('[data-protein]').forEach(button => {
        const active = button.dataset.protein === key;
        button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active));
      });
    }
    function populateTabs() {
      $('proteinTabs').replaceChildren();
      Object.keys(structures).forEach(id => {
        const button = document.createElement('button'); button.type = 'button'; button.textContent = proteinName(id);
        button.dataset.protein = id; button.title = structures[id].prepared ? `${proteinName(id)} · input ${id}` : proteinName(id);
        button.onclick = () => {key = id; loadStructure();}; $('proteinTabs').append(button);
      });
    }
    function showReferences(selected = requestedTarget) {
      structures = Object.fromEntries(referenceKeys.filter(id => references[id]).map(id => [id, references[id]]));
      key = selected; populateTabs(); loadStructure(); $('whole').textContent = 'Protein';
      $('viewerScope').textContent = 'Crystal reference ligands, not new candidate predictions · separate views, not aligned.';
    }
    function setPocket(value) {
      pocket = value;
      $('whole').classList.toggle('active', !value); $('pocket').classList.toggle('active', value);
      $('whole').setAttribute('aria-pressed', String(!value)); $('pocket').setAttribute('aria-pressed', String(value));
      renderers.forEach(view => {view.fit(); view.schedule();});
    }
    document.addEventListener('isoform:target', event => {
      requestedTarget = event.detail.target; referenceKeys = event.detail.targets || Object.keys(references);
      if (!preparedPayload) showReferences();
    });
    document.addEventListener('isoform:view', event => {if (!preparedPayload) {key = event.detail; loadStructure();}});
    document.addEventListener('isoform:library', event => {
      references = event.detail;
      if (!preparedPayload) showReferences(key);
    });
    document.addEventListener('sentinel:prepared', event => {
      if (event.detail === preparedPayload) return;
      preparedPayload = event.detail;
      if (!preparedPayload) {showReferences(); setPocket(false); return;}
      const entries = (preparedPayload.systems || []).map(system => {
        const ligand = new Set(system.ligand_atom_ids), byId = new Map(system.atoms.map(atom => [atom.id, atom]));
        const atoms = system.atoms.filter(atom => atom.element.toUpperCase() !== 'H').map(atom => ({
          p: atom.position, e: atom.element.toUpperCase(),
          group: ligand.has(atom.id) ? 'ligand' : atom.source?.residue === 'HEM' ? 'heme' : 'pocket', label: atom.id,
        }));
        const guides = (system.coordination || []).flatMap(pair => {
          const a = byId.get(pair.ids?.[0])?.position, b = byId.get(pair.ids?.[1])?.position;
          return validPoint(a) && validPoint(b) ? [{a, b}] : [];
        });
        return [system.id, {prepared: true, uploaded: preparedPayload.origin !== 'prepared-pair', protein_id: system.protein_id,
          atoms, backbone: [], center: average(atoms.map(atom => atom.p)), guides, ligand_label: system.ligand}];
      });
      structures = Object.fromEntries(entries);
      key = entries.find(([, structure]) => structure.protein_id === requestedTarget)?.[0] || entries[0]?.[0];
      comparisonKey = null; populateTabs(); setPocket(true); loadStructure(); $('whole').textContent = 'Whole pocket';
      const hasGuides = entries.some(([, structure]) => structure.guides.length);
      $('viewerScope').textContent = `Actual prepared inputs · ${hasGuides ? 'dashed lines show supplied coordination distances, not predicted interactions · ' : ''}separate views, not aligned.`;
    });
    document.addEventListener('isoform:run-state', event => {
      const state = event.detail || {}; $('structureExplorer').classList.toggle('is-running', Boolean(state.busy));
      $('viewerLive').querySelector('span').textContent = state.busy ? 'Computing' : 'Interactive 3D';
      $('viewerLive').title = state.text || '';
    });
    $('compareTarget').onchange = () => {comparisonKey = $('compareTarget').value; refreshComparison();};
    $('whole').onclick = () => setPocket(false); $('pocket').onclick = () => setPocket(true);
    $('rotate').onclick = () => {
      rotating = !rotating; $('rotate').classList.toggle('active', rotating); $('rotate').setAttribute('aria-pressed', String(rotating));
      renderers.forEach(view => view.schedule());
    };
    $('reset').onclick = () => renderers.forEach(view => view.reset());
    window.addEventListener('resize', () => renderers.forEach(view => view.resize()));
    document.addEventListener('visibilitychange', () => renderers.forEach(view => view.schedule()));
    populateTabs(); loadStructure(); renderers.forEach(view => {view.resize(); view.render();});
  } catch (error) {
    $('viewerError').hidden = false; $('molecule').hidden = true;
    $('comparePane').hidden = true; $('viewerGrid').classList.add('single');
    console.error('Protein viewer:', error);
  }
})();
