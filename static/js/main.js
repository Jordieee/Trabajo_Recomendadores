document.addEventListener('DOMContentLoaded', () => {
    // ── DOM refs ──────────────────────────────────────────────────────────────
    const userSelect       = document.getElementById('userSelect');
    const btnRecommend     = document.getElementById('btnRecommend');
    const tmdbKeyInput     = document.getElementById('tmdbKey');
    const algoTabs         = document.getElementById('algoTabs');
    const algoDescription  = document.getElementById('algoDescription');
    const formulaBadge     = document.getElementById('formulaBadge');
    const loadingText      = document.getElementById('loadingText');

    const initialState     = document.getElementById('initialState');
    const loadingState     = document.getElementById('loadingState');
    const resultsState     = document.getElementById('resultsState');
    const preferencesSection   = document.getElementById('preferencesSection');
    const neighborsSection     = document.getElementById('neighborsSection');
    const neighborsSectionTitle= document.getElementById('neighborsSectionTitle');
    const groupMembersSection  = document.getElementById('groupMembersSection');

    const preferencesContainer  = document.getElementById('preferencesContainer');
    const neighborsContainer    = document.getElementById('neighborsContainer');
    const groupMembersContainer = document.getElementById('groupMembersContainer');
    const moviesGrid            = document.getElementById('moviesGrid');

    // ── Group UI refs ─────────────────────────────────────────────────────────
    const userSelectorGroup   = document.getElementById('userSelectorGroup');
    const groupSelectorGroup  = document.getElementById('groupSelectorGroup');
    const aggregationGroup    = document.getElementById('aggregationGroup');
    const groupUserSelect     = document.getElementById('groupUserSelect');
    const btnAddMember        = document.getElementById('btnAddMember');
    const groupMembersList    = document.getElementById('groupMembersList');
    const aggregationSelect   = document.getElementById('aggregationSelect');
    const groupAlgoSelect     = document.getElementById('groupAlgoSelect');
    const dictatorRow         = document.getElementById('dictatorRow');
    const dictatorSelect      = document.getElementById('dictatorSelect');

    // ── Algorithm state ───────────────────────────────────────────────────────
    let currentAlgo = 'contenido';
    let groupMembers = []; // [{ id, label }]

    const MAX_GROUP = 10;

    const ALGO_META = {
        'contenido': {
            desc: 'Filtra por géneros preferidos del usuario',
            badge: 'r(u,i) = αA + βC + γF',
            badgeTitle: 'Fórmula: 0.5×Afinidad + 0.3×Calidad + 0.2×Fiabilidad',
            loading: 'Analizando catálogo y calculando r(u,i)...',
            apiUrl: (uid) => `/api/recommend/${uid}`,
        },
        'collab-uu': {
            desc: 'Usuarios con gustos similares recomiendan (Pearson)',
            badge: 'r̂(u,i) = μ_u + Σ sim·(r_v,i − μ_v) / Σ|sim|',
            badgeTitle: 'User-User: promedio ponderado por similitud Pearson',
            loading: 'Buscando vecinos similares y prediciendo ratings...',
            apiUrl: (uid) => `/api/recommend/collab-uu/${uid}`,
        },
        'collab-ii': {
            desc: 'Películas similares a las que ya valoraste (Pearson)',
            badge: 'r̂(u,i) = μ_i + Σ sim(i,j)·(r_u,j − μ_j) / Σ|sim|',
            badgeTitle: 'Item-Item: similitud Pearson entre ítems',
            loading: 'Calculando similitudes entre películas...',
            apiUrl: (uid) => `/api/recommend/collab-ii/${uid}`,
        },
        'hibrido': {
            desc: 'Ponderación de Contenido y Colaborativo (T5)',
            badge: 'r(u,i) = α·r_cont + β·r_col',
            badgeTitle: 'Híbrido Ponderado',
            loading: 'Calculando perfiles, combinando ratios...',
            apiUrl: (uid) => `/api/recommend/hibrido/${uid}`,
        },
        'grupo': {
            desc: 'Recomendación para un grupo de usuarios (T6)',
            badge: 'Agregación grupal: Borda / Miseria / Placer...',
            badgeTitle: 'SR de Grupos — Trabajo 6',
            loading: 'Calculando recomendaciones del grupo...',
            apiUrl: () => null, // Se construye dinámicamente
        },
    };

    const AGGREGATION_LABELS = {
        average: 'Media',
        average_without_misery: 'Media sin Miseria',
        multiplicative: 'Multiplicativa',
        additive_utilitarian: 'Suma Utilitaria',
        borda_count: 'Borda Count',
        plurality_voting: 'Pluralidad',
        approval_voting: 'Aprobación',
        least_misery: 'Least Misery',
        most_pleasure: 'Most Pleasure',
        dictatorship: 'Dictadura',
    };

    // ── Load users ────────────────────────────────────────────────────────────
    let allUsers = [];
    fetch('/api/users')
        .then(res => res.json())
        .then(users => {
            allUsers = users;
            userSelect.innerHTML = '<option value="">-- Elige un usuario --</option>';
            groupUserSelect.innerHTML = '<option value="">Seleccionar usuario...</option>';
            users.forEach(u => {
                const opt1 = document.createElement('option');
                opt1.value = u; opt1.textContent = `Usuario ID: ${u}`;
                userSelect.appendChild(opt1);

                const opt2 = document.createElement('option');
                opt2.value = u; opt2.textContent = `Usuario ${u}`;
                groupUserSelect.appendChild(opt2);
            });
        })
        .catch(err => {
            console.error('Error cargando usuarios', err);
            userSelect.innerHTML = '<option value="">Error de carga</option>';
        });

    userSelect.addEventListener('change', (e) => {
        btnRecommend.disabled = !e.target.value;
    });

    // ── Algorithm tab switching ───────────────────────────────────────────────
    algoTabs.querySelectorAll('.algo-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            algoTabs.querySelectorAll('.algo-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentAlgo = tab.dataset.algo;
            algoDescription.textContent = ALGO_META[currentAlgo].desc;

            if (currentAlgo === 'grupo') {
                userSelectorGroup.classList.add('hidden');
                groupSelectorGroup.classList.remove('hidden');
                aggregationGroup.classList.remove('hidden');
                updateGroupBtn();
            } else {
                userSelectorGroup.classList.remove('hidden');
                groupSelectorGroup.classList.add('hidden');
                aggregationGroup.classList.add('hidden');
                btnRecommend.disabled = !userSelect.value;
            }
        });
    });

    // ── Group member management ───────────────────────────────────────────────
    btnAddMember.addEventListener('click', () => {
        const uid = parseInt(groupUserSelect.value);
        if (!uid) return;
        if (groupMembers.find(m => m.id === uid)) return; // already added
        if (groupMembers.length >= MAX_GROUP) return;

        groupMembers.push({ id: uid, label: `Usuario ${uid}` });
        renderGroupMembers();
        updateGroupBtn();
        updateDictatorSelect();
    });

    function renderGroupMembers() {
        groupMembersList.innerHTML = '';
        groupMembers.forEach((m, idx) => {
            const chip = document.createElement('div');
            chip.className = 'member-chip';
            chip.innerHTML = `
                <i class="fa-solid fa-user-circle"></i>
                <span>U${m.id}</span>
                <button class="chip-remove" data-idx="${idx}" title="Eliminar"><i class="fa-solid fa-xmark"></i></button>
            `;
            chip.querySelector('.chip-remove').addEventListener('click', () => {
                groupMembers.splice(idx, 1);
                renderGroupMembers();
                updateGroupBtn();
                updateDictatorSelect();
            });
            groupMembersList.appendChild(chip);
        });
    }

    function updateGroupBtn() {
        btnRecommend.disabled = (currentAlgo === 'grupo') ? (groupMembers.length < 2) : !userSelect.value;
    }

    function updateDictatorSelect() {
        dictatorSelect.innerHTML = '';
        groupMembers.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            opt.textContent = `Usuario ${m.id}`;
            dictatorSelect.appendChild(opt);
        });
    }

    aggregationSelect.addEventListener('change', () => {
        if (aggregationSelect.value === 'dictatorship') {
            dictatorRow.classList.remove('hidden');
        } else {
            dictatorRow.classList.add('hidden');
        }
    });

    // ── Main CTA ──────────────────────────────────────────────────────────────
    btnRecommend.addEventListener('click', async () => {
        if (currentAlgo === 'grupo') {
            await fetchGrupo();
        } else {
            const userId = userSelect.value;
            if (!userId) return;
            await fetchIndividual(userId);
        }
    });

    async function fetchIndividual(userId) {
        const meta = ALGO_META[currentAlgo];

        initialState.classList.add('hidden');
        resultsState.classList.add('hidden');
        loadingState.classList.remove('hidden');
        loadingText.textContent = meta.loading;

        try {
            const res = await fetch(meta.apiUrl(userId));
            const data = await res.json();

            if (!res.ok) {
                alert(`Error: ${data.error}`);
                loadingState.classList.add('hidden');
                initialState.classList.remove('hidden');
                return;
            }

            formulaBadge.textContent = meta.badge;
            formulaBadge.title = meta.badgeTitle;

            preferencesSection.classList.add('hidden');
            neighborsSection.classList.add('hidden');
            groupMembersSection.classList.add('hidden');

            if (currentAlgo === 'contenido') {
                renderPreferences(data.preferencias || {});
                preferencesSection.classList.remove('hidden');
                await renderMoviesContent(data.recomendaciones);
            } else if (currentAlgo === 'collab-uu') {
                renderNeighbors(data.vecinos || [], 'usuarios');
                neighborsSection.classList.remove('hidden');
                await renderMoviesCollab(data.recomendaciones, 'uu');
            } else if (currentAlgo === 'hibrido') {
                renderPreferences(data.preferencias || {});
                renderNeighbors(data.vecinos || [], 'usuarios');
                preferencesSection.classList.remove('hidden');
                neighborsSection.classList.remove('hidden');
                formulaBadge.textContent = `r(u,i) = ${data.alpha}·Cont + ${data.beta}·Collab`;
                await renderMoviesHibrido(data.recomendaciones);
            } else {
                await renderMoviesCollab(data.recomendaciones, 'ii');
            }

            loadingState.classList.add('hidden');
            resultsState.classList.remove('hidden');

        } catch (err) {
            console.error(err);
            alert('Error al conectar con la API.');
            loadingState.classList.add('hidden');
            initialState.classList.remove('hidden');
        }
    }

    async function fetchGrupo() {
        const aggregation = aggregationSelect.value;
        const groupAlgo = groupAlgoSelect.value;
        const dictatorId = aggregation === 'dictatorship' ? dictatorSelect.value : null;
        const userIds = groupMembers.map(m => m.id).join(',');

        let url = `/api/recommend/grupo?user_ids=${userIds}&algorithm=${groupAlgo}&aggregation=${aggregation}`;
        if (dictatorId) url += `&dictator_id=${dictatorId}`;

        initialState.classList.add('hidden');
        resultsState.classList.add('hidden');
        loadingState.classList.remove('hidden');
        loadingText.textContent = `Calculando recomendaciones para el grupo (${AGGREGATION_LABELS[aggregation]})...`;

        try {
            const res = await fetch(url);
            const data = await res.json();

            if (!res.ok) {
                alert(`Error: ${data.error}`);
                loadingState.classList.add('hidden');
                initialState.classList.remove('hidden');
                return;
            }

            const aggLabel = AGGREGATION_LABELS[aggregation] || aggregation;
            formulaBadge.textContent = `Grupo: ${aggLabel} (${groupAlgo})`;
            formulaBadge.title = 'Recomendación para grupo — Trabajo 6';

            preferencesSection.classList.add('hidden');
            neighborsSection.classList.add('hidden');

            renderGroupMembersPanel(groupMembers, data.recomendaciones);
            groupMembersSection.classList.remove('hidden');

            await renderMoviesGrupo(data.recomendaciones, groupMembers);

            loadingState.classList.add('hidden');
            resultsState.classList.remove('hidden');

        } catch (err) {
            console.error(err);
            alert('Error al conectar con la API.');
            loadingState.classList.add('hidden');
            initialState.classList.remove('hidden');
        }
    }

    // ── Render: Content-based preferences ────────────────────────────────────
    function renderPreferences(prefObj) {
        preferencesContainer.innerHTML = '';
        const sortedPrefs = Object.entries(prefObj).sort((a, b) => b[1] - a[1]);
        const maxVal = sortedPrefs.length > 0 ? sortedPrefs[0][1] : 1;

        sortedPrefs.forEach(([genre, value]) => {
            const percentage = (value / maxVal) * 100;
            const card = document.createElement('div');
            card.className = 'pref-card';
            card.innerHTML = `
                <div class="pref-name">
                    <span>${genre}</span>
                    <span class="text-muted">${value.toFixed(3)}</span>
                </div>
                <div class="pref-bar-bg">
                    <div class="pref-bar-fill" style="width: 0%"></div>
                </div>
            `;
            preferencesContainer.appendChild(card);
            setTimeout(() => {
                card.querySelector('.pref-bar-fill').style.width = `${percentage}%`;
            }, 50);
        });
    }

    // ── Render: Neighbors (User-User) ─────────────────────────────────────────
    function renderNeighbors(neighbors, type) {
        neighborsContainer.innerHTML = '';
        neighborsSectionTitle.innerHTML = `<i class="fa-solid fa-users"></i> Vecinos más similares`;

        if (!neighbors.length) {
            neighborsContainer.innerHTML = '<p style="color:var(--text-muted)">No se encontraron vecinos.</p>';
            return;
        }

        const maxSim = neighbors[0].similitud || 1;
        neighbors.forEach(n => {
            const pct = ((n.similitud / maxSim) * 100).toFixed(0);
            const badge = document.createElement('div');
            badge.className = 'pref-card';
            badge.innerHTML = `
                <div class="pref-name">
                    <span><i class="fa-solid fa-user-circle"></i> Usuario ${n.userId}</span>
                    <span class="text-muted">sim: ${n.similitud.toFixed(3)}</span>
                </div>
                <div class="pref-bar-bg">
                    <div class="pref-bar-fill" style="width:0%; background: linear-gradient(90deg, #06b6d4, #3b82f6)"></div>
                </div>
            `;
            neighborsContainer.appendChild(badge);
            setTimeout(() => {
                badge.querySelector('.pref-bar-fill').style.width = `${pct}%`;
            }, 50);
        });
    }

    // ── Render: Group members panel ───────────────────────────────────────────
    function renderGroupMembersPanel(members, recommendations) {
        groupMembersContainer.innerHTML = '';

        members.forEach(m => {
            // Aggregate score for member across all recommendations
            let totalScore = 0, count = 0;
            recommendations.forEach(r => {
                const s = r.individual_scores?.[String(m.id)];
                if (s !== null && s !== undefined) { totalScore += s; count++; }
            });
            const avgScore = count > 0 ? totalScore / count : 0;
            const pct = (avgScore * 100).toFixed(0);

            const card = document.createElement('div');
            card.className = 'pref-card';
            card.innerHTML = `
                <div class="pref-name">
                    <span><i class="fa-solid fa-user-circle"></i> Usuario ${m.id}</span>
                    <span class="text-muted">${avgScore.toFixed(3)}</span>
                </div>
                <div class="pref-bar-bg">
                    <div class="pref-bar-fill member-bar" style="width:0%; background: linear-gradient(90deg, #a855f7, #ec4899)"></div>
                </div>
            `;
            groupMembersContainer.appendChild(card);
            setTimeout(() => {
                card.querySelector('.member-bar').style.width = `${pct}%`;
            }, 50);
        });
    }

    // ── Render: Content-based movie cards ─────────────────────────────────────
    async function renderMoviesContent(movies) {
        moviesGrid.innerHTML = '';
        const apiKey = tmdbKeyInput.value.trim();

        for (let i = 0; i < movies.length; i++) {
            const m = movies[i];
            const rank = i + 1;
            const card = document.createElement('article');
            card.className = 'movie-card';

            const cleanTitle = m.titulo.replace(/\s*\(\d{4}\)\s*$/, '');
            let posterUrl = `https://via.placeholder.com/300x450/1e293b/94a3b8?text=${encodeURIComponent(cleanTitle)}`;

            if (apiKey) {
                try {
                    const searchUrl = `https://api.themoviedb.org/3/search/movie?api_key=${apiKey}&query=${encodeURIComponent(cleanTitle)}&language=es-ES`;
                    const res = await fetch(searchUrl);
                    const data = await res.json();
                    if (data.results && data.results.length > 0 && data.results[0].poster_path) {
                        posterUrl = `https://image.tmdb.org/t/p/w500${data.results[0].poster_path}`;
                    }
                } catch (e) { }
            }

            const tagsHtml = (m.generos_match || '').split(',')
                .filter(g => g.trim())
                .map(g => `<span class="explain-tag">${g.trim()}</span>`)
                .join('');

            const scaledScore = m.score_final * 5;
            const starsHtml = getStarsHTML(scaledScore);

            card.innerHTML = `
                <div class="rank-badge">#${rank}</div>
                <div class="movie-poster-container">
                    <img class="movie-poster" src="${posterUrl}" alt="Póster de ${m.titulo}" loading="lazy">
                </div>
                <div class="movie-info">
                    <h4 class="movie-title">${m.titulo}</h4>
                    <div class="explain-tags">${tagsHtml}</div>
                    <div class="score-details">
                        <div class="score-row">
                            <span>Afinidad (${(m.score_afinidad * 100).toFixed(1)}%)</span>
                            <div class="score-bar-bg"><div class="score-bar-fill fill-afinidad" style="width: ${m.score_afinidad * 100}%"></div></div>
                        </div>
                        <div class="score-row">
                            <span>Calidad (${m.puntuacion.toFixed(1)}/10)</span>
                            <div class="score-bar-bg"><div class="score-bar-fill fill-calidad" style="width: ${m.score_calidad * 100}%"></div></div>
                        </div>
                        <div class="score-row">
                            <span>Fiabilidad</span>
                            <div class="score-bar-bg"><div class="score-bar-fill fill-fiabilidad" style="width: ${m.score_fiabilidad * 100}%"></div></div>
                        </div>
                    </div>
                </div>
                <div class="score-final-wrap">
                    <div class="star-rating">${starsHtml}</div>
                    <div class="score-text">${m.score_final.toFixed(3)}</div>
                </div>
            `;
            moviesGrid.appendChild(card);
        }
    }

    // ── Render: Collaborative movie cards (UU or II) ──────────────────────────
    async function renderMoviesCollab(movies, mode) {
        moviesGrid.innerHTML = '';
        const apiKey = tmdbKeyInput.value.trim();

        for (let i = 0; i < movies.length; i++) {
            const m = movies[i];
            const rank = i + 1;
            const card = document.createElement('article');
            card.className = 'movie-card';

            const cleanTitle = m.titulo.replace(/\s*\(\d{4}\)\s*$/, '');
            let posterUrl = `https://via.placeholder.com/300x450/1e293b/94a3b8?text=${encodeURIComponent(cleanTitle)}`;

            if (apiKey) {
                try {
                    const searchUrl = `https://api.themoviedb.org/3/search/movie?api_key=${apiKey}&query=${encodeURIComponent(cleanTitle)}&language=es-ES`;
                    const res = await fetch(searchUrl);
                    const data = await res.json();
                    if (data.results && data.results.length > 0 && data.results[0].poster_path) {
                        posterUrl = `https://image.tmdb.org/t/p/w500${data.results[0].poster_path}`;
                    }
                } catch (e) { }
            }

            const simPct = Math.min(100, Math.max(0, (m.sim_avg || 0) * 100));

            let basePillsHtml = '';
            if (mode === 'ii' && m.items_base && m.items_base.length > 0) {
                basePillsHtml = `
                    <div class="explain-tags" style="margin-top: 0.25rem;">
                        ${m.items_base.map(t => `<span class="explain-tag tag-item">${t.replace(/\s*\(\d{4}\)$/, '')}</span>`).join('')}
                    </div>
                `;
            }

            const starsHtml = getStarsHTML(m.pred_rating);

            const simColor = mode === 'uu'
                ? 'linear-gradient(90deg, #06b6d4, #3b82f6)'
                : 'linear-gradient(90deg, #f59e0b, #ef4444)';

            const modeLabel = mode === 'uu'
                ? `<span class="algo-pill pill-uu">Usuario-Usuario</span>`
                : `<span class="algo-pill pill-ii">Ítem-Ítem</span>`;

            const nInfo = mode === 'uu'
                ? `${m.n_vecinos} vecinos`
                : `${m.n_items} ítems base`;

            card.innerHTML = `
                <div class="rank-badge">#${rank}</div>
                <div class="movie-poster-container">
                    <img class="movie-poster" src="${posterUrl}" alt="Póster de ${m.titulo}" loading="lazy">
                </div>
                <div class="movie-info">
                    <h4 class="movie-title">${m.titulo}</h4>
                    ${modeLabel}
                    ${basePillsHtml}
                    <div class="score-details" style="margin-top: auto;">
                        <div class="score-row">
                            <span>Similitud media</span>
                            <div class="score-bar-bg">
                                <div class="score-bar-fill" style="width: ${simPct}%; background: ${simColor}"></div>
                            </div>
                            <span style="min-width:38px; text-align:right">${(m.sim_avg || 0).toFixed(2)}</span>
                        </div>
                        <div class="score-row">
                            <span>Basado en</span>
                            <div class="score-bar-bg"></div>
                            <span style="min-width:80px; text-align:right; font-size:0.8rem; color:var(--text-muted)">${nInfo}</span>
                        </div>
                    </div>
                </div>
                <div class="score-final-wrap">
                    <div class="star-rating">${starsHtml}</div>
                    <div class="score-text collab-pred">${m.pred_rating.toFixed(2)}<span class="pred-suffix">/5</span></div>
                </div>
            `;
            moviesGrid.appendChild(card);
        }
    }

    // ── Render: Hibrido movie cards ───────────────────────────────────────────
    async function renderMoviesHibrido(movies) {
        moviesGrid.innerHTML = '';
        const apiKey = tmdbKeyInput.value.trim();

        for (let i = 0; i < movies.length; i++) {
            const m = movies[i];
            const rank = i + 1;
            const card = document.createElement('article');
            card.className = 'movie-card';

            const cleanTitle = m.titulo.replace(/\s*\(\d{4}\)\s*$/, '');
            let posterUrl = `https://via.placeholder.com/300x450/1e293b/94a3b8?text=${encodeURIComponent(cleanTitle)}`;

            if (apiKey) {
                try {
                    const searchUrl = `https://api.themoviedb.org/3/search/movie?api_key=${apiKey}&query=${encodeURIComponent(cleanTitle)}&language=es-ES`;
                    const res = await fetch(searchUrl);
                    const data = await res.json();
                    if (data.results && data.results.length > 0 && data.results[0].poster_path) {
                        posterUrl = `https://image.tmdb.org/t/p/w500${data.results[0].poster_path}`;
                    }
                } catch (e) { }
            }

            const inCont = m.en_cont ? '<span class="algo-pill pill-uu" style="background:#e74c3c;">Contenido</span>' : '';
            const inCol  = m.en_col  ? '<span class="algo-pill pill-ii" style="background:#3b82f6;">Colaborativo</span>' : '';

            const starsHtml = getStarsHTML(m.score_hibrido * 5);

            card.innerHTML = `
                <div class="rank-badge">#${rank}</div>
                <div class="movie-poster-container">
                    <img class="movie-poster" src="${posterUrl}" alt="Póster de ${m.titulo}" loading="lazy">
                </div>
                <div class="movie-info">
                    <h4 class="movie-title">${m.titulo}</h4>
                    <div style="margin-top: 5px">${inCont} ${inCol}</div>
                    <div class="score-details" style="margin-top: auto;">
                        <div class="score-row">
                            <span>Punt. Basado Cont.</span>
                            <div class="score-bar-bg">
                                <div class="score-bar-fill fill-afinidad" style="width: ${m.score_cont * 100}%"></div>
                            </div>
                            <span style="min-width:38px; text-align:right">${(m.score_cont).toFixed(2)}</span>
                        </div>
                        <div class="score-row">
                            <span>Punt. Colaborativo</span>
                            <div class="score-bar-bg">
                                <div class="score-bar-fill fill-calidad" style="width: ${m.score_col * 100}%"></div>
                            </div>
                            <span style="min-width:38px; text-align:right">${(m.score_col).toFixed(2)}</span>
                        </div>
                    </div>
                </div>
                <div class="score-final-wrap">
                    <div class="star-rating">${starsHtml}</div>
                    <div class="score-text collab-pred">${m.score_hibrido.toFixed(3)}</div>
                </div>
            `;
            moviesGrid.appendChild(card);
        }
    }

    // ── Render: Group movie cards (Trabajo 6) ─────────────────────────────────
    async function renderMoviesGrupo(movies, members) {
        moviesGrid.innerHTML = '';
        const apiKey = tmdbKeyInput.value.trim();
        // Build color palette for members
        const memberColors = ['#a855f7','#ec4899','#06b6d4','#f59e0b','#10b981','#ef4444','#3b82f6','#8b5cf6','#14b8a6','#f97316'];

        for (let i = 0; i < movies.length; i++) {
            const m = movies[i];
            const rank = i + 1;
            const card = document.createElement('article');
            card.className = 'movie-card';

            const cleanTitle = m.titulo.replace(/\s*\(\d{4}\)\s*$/, '');
            let posterUrl = `https://via.placeholder.com/300x450/1e293b/94a3b8?text=${encodeURIComponent(cleanTitle)}`;

            if (apiKey) {
                try {
                    const searchUrl = `https://api.themoviedb.org/3/search/movie?api_key=${apiKey}&query=${encodeURIComponent(cleanTitle)}&language=es-ES`;
                    const res = await fetch(searchUrl);
                    const data = await res.json();
                    if (data.results && data.results.length > 0 && data.results[0].poster_path) {
                        posterUrl = `https://image.tmdb.org/t/p/w500${data.results[0].poster_path}`;
                    }
                } catch (e) { }
            }

            // Build per-member score rows
            let memberScoresHtml = '';
            members.forEach((mem, idx) => {
                const sc = m.individual_scores?.[String(mem.id)];
                const hasScore = sc !== null && sc !== undefined;
                const pct = hasScore ? Math.round(sc * 100) : 0;
                const color = memberColors[idx % memberColors.length];
                memberScoresHtml += `
                    <div class="score-row">
                        <span style="color:${color}; min-width:55px">U${mem.id}</span>
                        <div class="score-bar-bg">
                            <div class="score-bar-fill" style="width:${pct}%; background:${color}"></div>
                        </div>
                        <span style="min-width:36px; text-align:right; font-size:0.8rem">${hasScore ? sc.toFixed(2) : '—'}</span>
                    </div>
                `;
            });

            const groupPct = Math.round((m.group_score || 0) * 100);
            const starsHtml = getStarsHTML(m.group_score * 5);

            card.innerHTML = `
                <div class="rank-badge">#${rank}</div>
                <div class="movie-poster-container">
                    <img class="movie-poster" src="${posterUrl}" alt="Póster de ${m.titulo}" loading="lazy">
                </div>
                <div class="movie-info">
                    <h4 class="movie-title">${m.titulo}</h4>
                    <span class="algo-pill pill-grupo"><i class="fa-solid fa-people-group"></i> Grupo</span>
                    <div class="score-details" style="margin-top:0.5rem;">
                        <div class="score-row" style="margin-bottom:0.25rem;">
                            <span style="font-weight:700; color:var(--primary)">Score grupal</span>
                            <div class="score-bar-bg">
                                <div class="score-bar-fill" style="width:${groupPct}%; background:linear-gradient(90deg,#8b5cf6,#ec4899)"></div>
                            </div>
                            <span style="min-width:36px; text-align:right; font-weight:700">${m.group_score.toFixed(3)}</span>
                        </div>
                        <div class="member-scores-divider"></div>
                        ${memberScoresHtml}
                    </div>
                </div>
                <div class="score-final-wrap">
                    <div class="star-rating">${starsHtml}</div>
                    <div class="score-text grupo-score">${m.group_score.toFixed(3)}</div>
                </div>
            `;
            moviesGrid.appendChild(card);
        }
    }

    // ── Helper: stars HTML ────────────────────────────────────────────────────
    function getStarsHTML(ratingOutOf5) {
        let html = '';
        for (let i = 1; i <= 5; i++) {
            if (ratingOutOf5 >= i - 0.25) {
                html += '<i class="fa-solid fa-star"></i>';
            } else if (ratingOutOf5 >= i - 0.75) {
                html += '<i class="fa-solid fa-star-half-stroke"></i>';
            } else {
                html += '<i class="fa-regular fa-star"></i>';
            }
        }
        return html;
    }
});
