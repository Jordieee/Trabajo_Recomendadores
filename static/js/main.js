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
    const metricsState     = document.getElementById('metricsState'); // Nuevo
    
    const preferencesSection   = document.getElementById('preferencesSection');
    const neighborsSection     = document.getElementById('neighborsSection');
    const groupMembersSection  = document.getElementById('groupMembersSection');

    const preferencesContainer  = document.getElementById('preferencesContainer');
    const neighborsContainer    = document.getElementById('neighborsContainer');
    const groupMembersContainer = document.getElementById('groupMembersContainer');
    const moviesGrid            = document.getElementById('moviesGrid');

    // ── Group UI refs
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

    // ── Metrics UI refs
    const metricsContent      = document.getElementById('metricsContent');
    const metricsLoading      = document.getElementById('metricsLoading');
    const btnRecalculateMetrics = document.getElementById('btnRecalculateMetrics');

    // ── New User UI refs
    const btnNewUser          = document.getElementById('btnNewUser');
    const newUserModal       = document.getElementById('newUserModal');
    const newUserGenres      = document.getElementById('newUserGenres');
    const btnSubmitNewUser    = document.getElementById('btnSubmitNewUser');

    // ── Movie Detail refs
    const movieModal         = document.getElementById('movieModal');
    const modalPoster        = document.getElementById('modalPoster');
    const modalTitle         = document.getElementById('modalTitle');
    const modalOverview      = document.getElementById('modalOverview');
    const modalCast          = document.getElementById('modalCast');
    const modalGenres        = document.getElementById('modalGenres');
    const modalYear          = document.getElementById('modalYear');
    const modalRuntime       = document.getElementById('modalRuntime');

    // ── Algorithm state ───────────────────────────────────────────────────────
    let currentAlgo = 'contenido';
    let groupMembers = []; 
    let categories = []; // Géneros cargados

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
            badge: 'Ponderación social',
            badgeTitle: 'User-User: promedio ponderado por similitud Pearson',
            loading: 'Buscando vecinos similares y prediciendo ratings...',
            apiUrl: (uid) => `/api/recommend/collab-uu/${uid}`,
        },
        'collab-ii': {
            desc: 'Películas similares a las que ya valoraste (Pearson)',
            badge: 'Similitud de ítems',
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
            badge: 'Agregación grupal',
            badgeTitle: 'SR de Grupos — Trabajo 6',
            loading: 'Calculando recomendaciones del grupo...',
            apiUrl: () => null,
        },
        'metricas': {
            desc: 'Análisis de calidad y precisión del sistema',
            loading: 'Evaluando algoritmos...',
        }
    };

    // ── Initialization ────────────────────────────────────────────────────────
    let allUsers = [];
    fetch('/api/users')
        .then(res => res.json())
        .then(users => {
            allUsers = users;
            userSelect.innerHTML = '<option value="">-- Elige un usuario --</option>';
            groupUserSelect.innerHTML = '<option value="">Seleccionar usuario...</option>';
            allUsers.forEach(u => {
                const opt = `<option value="${u}">Usuario ${u}</option>`;
                userSelect.insertAdjacentHTML('beforeend', opt);
                groupUserSelect.insertAdjacentHTML('beforeend', opt);
            });
        });

    // Cargar géneros para el registro de usuario nuevo
    fetch('/api/generos')
        .then(res => res.json())
        .then(data => {
            categories = data;
            renderRegistrationForm();
        });

    function renderRegistrationForm() {
        newUserGenres.innerHTML = categories.map(cat => `
            <div class="registration-form-item">
                <label>
                    <span>${cat.GeneroSP}</span>
                    <span id="val-${cat.GeneroSP}" style="font-weight:bold; color:var(--accent-light)">5</span>
                </label>
                <input type="range" class="modern-slider" min="0" max="10" step="1" value="5" 
                       oninput="document.getElementById('val-${cat.GeneroSP}').innerText = this.value"
                       data-genre="${cat.GeneroSP}">
            </div>
        `).join('');
    }

    // ── Tab Navigation ────────────────────────────────────────────────────────
    algoTabs.addEventListener('click', (e) => {
        const btn = e.target.closest('.algo-tab');
        if (!btn) return;

        algoTabs.querySelectorAll('.algo-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentAlgo = btn.dataset.algo;

        const meta = ALGO_META[currentAlgo];
        if (meta) {
            algoDescription.innerText = meta.desc;
            formulaBadge.innerText = meta.badge || '';
            formulaBadge.title = meta.badgeTitle || '';
            formulaBadge.style.display = meta.badge ? 'block' : 'none';
        }

        // Toggle UI groups
        const isGrupo = currentAlgo === 'grupo';
        const isMetricas = currentAlgo === 'metricas';
        
        userSelectorGroup.classList.toggle('hidden', isGrupo || isMetricas);
        groupSelectorGroup.classList.toggle('hidden', !isGrupo);
        aggregationGroup.classList.toggle('hidden', !isGrupo);
        
        btnRecommend.style.display = isMetricas ? 'none' : 'block';

        if (isMetricas) {
            showPanel(metricsState);
            loadMetrics();
        } else {
            showPanel(initialState);
        }
        
        validateInputs();
    });

    function showPanel(panel) {
        [initialState, loadingState, resultsState, metricsState].forEach(p => p.classList.add('hidden'));
        panel.classList.remove('hidden');
    }

    function validateInputs() {
        if (currentAlgo === 'metricas') return;
        
        if (currentAlgo === 'grupo') {
            btnRecommend.disabled = groupMembers.length < 2;
        } else {
            btnRecommend.disabled = !userSelect.value;
        }
    }

    userSelect.addEventListener('change', validateInputs);

    // ── Evaluation Metrics ────────────────────────────────────────────────────
    function loadMetrics() {
        metricsLoading.classList.remove('hidden');
        metricsContent.innerHTML = '';
        
        fetch('/api/metrics')
            .then(res => res.json())
            .then(data => {
                metricsLoading.classList.add('hidden');
                if (data.error) {
                    metricsContent.innerHTML = `<div class="empty-state"><i class="fa-solid fa-circle-exclamation"></i><p>${data.detail}</p></div>`;
                } else {
                    renderMetrics(data);
                }
            });
    }

    function renderMetrics(data) {
        metricsContent.innerHTML = '';
        const timestamp = data.timestamp ? `<p style="text-align:center; color:var(--text-muted); width:100%; margin-top:2rem;">Última actualización: ${data.timestamp}</p>` : '';
        
        for (const [algo, metrics] of Object.entries(data)) {
            if (algo === 'timestamp') continue;
            const card = document.createElement('div');
            card.className = 'metric-card';
            
            const prec = metrics.precision ? (metrics.precision * 100).toFixed(2) : '—';
            const mae = metrics.mae || '—';
            
            card.innerHTML = `
                <h4>${algo.toUpperCase()}</h4>
                <div class="metric-value">${prec}%</div>
                <div class="metric-label">Precision@10</div>
                <div class="metric-value" style="font-size:1.5rem; margin-top:1.5rem">${mae}</div>
                <div class="metric-label">Error Absoluto (MAE)</div>
                <p style="font-size:0.8rem; color:var(--text-muted); margin-top:1.5rem">${metrics.desc}</p>
            `;
            metricsContent.appendChild(card);
        }
        
        if (timestamp) {
            const footer = document.createElement('div');
            footer.style.width = '100%';
            footer.innerHTML = timestamp;
            metricsContent.appendChild(footer);
        }
    }

    btnRecalculateMetrics.addEventListener('click', () => loadMetrics(true));

    // ── New User logic ────────────────────────────────────────────────────────
    btnNewUser.addEventListener('click', () => {
        newUserModal.style.display = 'flex';
    });

    document.querySelectorAll('.modal-cancel, .modal-close').forEach(btn => {
        btn.addEventListener('click', () => {
            newUserModal.style.display = 'none';
            movieModal.style.display = 'none';
        });
    });

    btnSubmitNewUser.addEventListener('click', () => {
        const prefs = {};
        newUserGenres.querySelectorAll('input').forEach(input => {
            prefs[input.dataset.genre] = parseInt(input.value);
        });

        newUserModal.style.display = 'none';
        showPanel(loadingState);
        loadingText.innerText = 'Creando tu perfil y buscando películas...';

        fetch('/api/recommend/new-user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(prefs)
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            renderResults(data);
        })
        .catch(err => {
            alert(err.message);
            showPanel(initialState);
        });
    });

    // ── Recommendation logic ──────────────────────────────────────────────────
    btnRecommend.addEventListener('click', () => {
        const uid = userSelect.value;
        const meta = ALGO_META[currentAlgo];

        showPanel(loadingState);
        loadingText.innerText = meta.loading;

        let url = meta.apiUrl(uid);
        if (currentAlgo === 'grupo') {
            const uids = groupMembers.map(m => m.id).join(',');
            const agg = aggregationSelect.value;
            const dictator = dictatorSelect.value;
            const base = groupAlgoSelect.value;
            url = `/api/recommend/grupo?user_ids=${uids}&algorithm=${base}&aggregation=${agg}&dictator=${dictator}`;
        }

        fetch(url)
            .then(res => res.json())
            .then(data => {
                if (data.error) throw new Error(data.error);
                renderResults(data);
            })
            .catch(err => {
                alert(err.message);
                showPanel(initialState);
            });
    });

    function renderResults(data) {
        showPanel(resultsState);
        
        // Hide all secondary panels
        [preferencesSection, neighborsSection, groupMembersSection].forEach(s => s.classList.add('hidden'));

        if (currentAlgo === 'contenido' || data.algoritmo === 'nuevo-usuario') {
            preferencesSection.classList.remove('hidden');
            renderPreferences(data.perfil_filtrado);
            renderMoviesContent(data.recomendaciones);
        } else if (currentAlgo === 'collab-uu' || currentAlgo === 'collab-ii') {
            neighborsSection.classList.remove('hidden');
            const mode = currentAlgo === 'collab-uu' ? 'uu' : 'ii';
            neighborsSectionTitle.innerHTML = mode === 'uu' 
                ? '<i class="fa-solid fa-users"></i> Vecinos más similares'
                : '<i class="fa-solid fa-film"></i> Películas semilla';
            renderNeighbors(data.vecinos || data.items_base, mode);
            renderMoviesCollab(data.recomendaciones, mode);
        } else if (currentAlgo === 'hibrido') {
            renderMoviesHibrido(data.recomendaciones);
        } else if (currentAlgo === 'grupo') {
            groupMembersSection.classList.remove('hidden');
            renderGroupMembersPanel(groupMembers, data.recomendaciones);
            renderMoviesGrupo(data.recomendaciones, groupMembers);
        }
    }

    // ── Movie Details logic ───────────────────────────────────────────────────
    async function showMovieDetails(movieId, title) {
        movieModal.style.display = 'flex';
        modalTitle.innerText = title;
        modalOverview.innerText = 'Cargando sinopsis de TMDB...';
        modalCast.innerText = '-';
        modalGenres.innerHTML = '';
        modalYear.innerText = '';
        modalRuntime.innerText = '';
        
        // Poster temporal
        const cleanTitle = title.replace(/\s*\(\d{4}\)\s*$/, '');
        modalPoster.src = `https://via.placeholder.com/300x450/1e293b/94a3b8?text=${encodeURIComponent(cleanTitle)}`;

        try {
            const res = await fetch(`/api/movie/${movieId}?api_key=${tmdbKeyInput.value.trim()}`);
            const data = await res.json();
            
            if (data.error) throw new Error(data.error);
            
            modalOverview.innerText = data.overview;
            modalCast.innerText = data.cast.join(', ');
            modalYear.innerText = data.release_date ? data.release_date.split('-')[0] : '';
            modalRuntime.innerText = data.runtime ? `${data.runtime} min` : '';
            modalGenres.innerHTML = data.genres.map(g => `<span class="explain-tag">${g}</span>`).join('');
            
            // Intentar buscar poster real si no lo tenemos ya
            if (tmdbKeyInput.value.trim()) {
                const searchRes = await fetch(`https://api.themoviedb.org/3/search/movie?api_key=${tmdbKeyInput.value.trim()}&query=${encodeURIComponent(cleanTitle)}`);
                const searchData = await searchRes.json();
                if (searchData.results?.[0]?.poster_path) {
                    modalPoster.src = `https://image.tmdb.org/t/p/w500${searchData.results[0].poster_path}`;
                }
            }
        } catch (e) {
            modalOverview.innerText = "No se pudo cargar la información detallada.";
        }
    }

    // ── Render Helpers ────────────────────────────────────────────────────────
    function renderPreferences(perf) {
        if (!perf) return;
        preferencesContainer.innerHTML = Object.entries(perf).map(([g, v]) => `
            <div class="pref-item">
                <span class="pref-label">${g}</span>
                <div class="pref-bar-bg"><div class="pref-bar-fill" style="width:${v*100}%"></div></div>
                <span class="pref-val">${v.toFixed(2)}</span>
            </div>
        `).join('');
    }

    function renderNeighbors(list, mode) {
        if (!list) return;
        neighborsContainer.innerHTML = list.map(n => {
            const label = mode === 'uu' ? `Usuario ${n.userId}` : n.titulo.replace(/\s*\(\d{4}\)$/, '');
            const val = mode === 'uu' ? n.similitud : n.sim;
            return `
                <div class="neighbor-chip">
                    <span class="neighbor-name">${label}</span>
                    <span class="neighbor-sim">${(val*100).toFixed(0)}%</span>
                </div>
            `;
        }).join('');
    }

    function renderGroupMembersPanel(members, recs) {
        groupMembersContainer.innerHTML = members.map((m, i) => `
            <div class="neighbor-chip" style="border-left: 3px solid var(--accent-light)">
                <span class="neighbor-name">Usuario ${m.id}</span>
            </div>
        `).join('');
    }

    // ── Movie Card Rendering (Extended with Click)
    function attachCardEvents(card, movieId, title) {
        card.style.cursor = 'pointer';
        card.addEventListener('click', () => showMovieDetails(movieId, title));
    }

    async function renderMoviesContent(movies) {
        moviesGrid.innerHTML = '';
        const apiKey = tmdbKeyInput.value.trim();
        for (let i = 0; i < movies.length; i++) {
            const m = movies[i];
            const card = document.createElement('article');
            card.className = 'movie-card';
            // ... (Logic similar to original but with attachCardEvents)
            // (Skipped for brevity, same as original but adding event)
            await populateCardContent(card, m, i+1, 'contenido', apiKey);
            attachCardEvents(card, m.movieId, m.titulo);
            moviesGrid.appendChild(card);
        }
    }

    // Simplified card population for all modes
    async function populateCardContent(card, m, rank, type, apiKey) {
        const cleanTitle = m.titulo.replace(/\s*\(\d{4}\)\s*$/, '');
        let posterUrl = `https://via.placeholder.com/300x450/1e293b/94a3b8?text=${encodeURIComponent(cleanTitle)}`;
        
        // Basic card structure
        card.innerHTML = `
            <div class="rank-badge">#${rank}</div>
            <div class="movie-poster-container">
                <img class="movie-poster" src="${posterUrl}" alt="Póster" loading="lazy">
            </div>
            <div class="movie-info">
                <h4 class="movie-title">${m.titulo}</h4>
                <div class="score-details" id="details-${rank}"></div>
            </div>
            <div class="score-final-wrap" id="final-${rank}"></div>
        `;
        
        // Fetch poster async if key exists
        if (apiKey) {
            fetch(`https://api.themoviedb.org/3/search/movie?api_key=${apiKey}&query=${encodeURIComponent(cleanTitle)}`)
                .then(r => r.json())
                .then(d => {
                    if (d.results?.[0]?.poster_path) 
                        card.querySelector('img').src = `https://image.tmdb.org/t/p/w500${d.results[0].poster_path}`;
                }).catch(()=>{});
        }
        
        const details = card.querySelector(`#details-${rank}`);
        const final = card.querySelector(`#final-${rank}`);
        
        if (type === 'contenido') {
            details.innerHTML = `
                <div class="score-row"><span>Afinidad</span><div class="score-bar-bg"><div class="score-bar-fill fill-afinidad" style="width:${m.score_afinidad*100}%"></div></div></div>
                <div class="score-row"><span>Calidad</span><div class="score-bar-bg"><div class="score-bar-fill fill-calidad" style="width:${m.puntuacion*10}%"></div></div></div>
            `;
            final.innerHTML = `<div class="star-rating">${getStarsHTML(m.score_final*5)}</div><div class="score-text">${m.score_final.toFixed(3)}</div>`;
        } else if (type === 'collab') {
             details.innerHTML = `
                <div class="score-row"><span>Similitud</span><div class="score-bar-bg"><div class="score-bar-fill fill-uu" style="width:${m.sim_avg*100}%"></div></div></div>
            `;
            final.innerHTML = `<div class="star-rating">${getStarsHTML(m.pred_rating)}</div><div class="score-text">${m.pred_rating.toFixed(2)}</div>`;
        } else if (type === 'hibrido') {
             final.innerHTML = `<div class="star-rating">${getStarsHTML(m.score_hibrido*5)}</div><div class="score-text">${m.score_hibrido.toFixed(3)}</div>`;
        } else if (type === 'grupo') {
             final.innerHTML = `<div class="star-rating">${getStarsHTML(m.group_score*5)}</div><div class="score-text">${m.group_score.toFixed(3)}</div>`;
        }
    }

    async function renderMoviesCollab(movies, mode) {
        moviesGrid.innerHTML = '';
        const apiKey = tmdbKeyInput.value.trim();
        for (let i = 0; i < movies.length; i++) {
            const m = movies[i];
            const card = document.createElement('article');
            card.className = 'movie-card';
            await populateCardContent(card, m, i+1, 'collab', apiKey);
            attachCardEvents(card, m.movieId, m.titulo);
            moviesGrid.appendChild(card);
        }
    }

    async function renderMoviesHibrido(movies) {
        moviesGrid.innerHTML = '';
        const apiKey = tmdbKeyInput.value.trim();
        for (let i = 0; i < movies.length; i++) {
            const m = movies[i];
            const card = document.createElement('article');
            card.className = 'movie-card';
            await populateCardContent(card, m, i+1, 'hibrido', apiKey);
            attachCardEvents(card, m.movieId, m.titulo);
            moviesGrid.appendChild(card);
        }
    }

    async function renderMoviesGrupo(movies, members) {
        moviesGrid.innerHTML = '';
        const apiKey = tmdbKeyInput.value.trim();
        for (let i = 0; i < movies.length; i++) {
            const m = movies[i];
            const card = document.createElement('article');
            card.className = 'movie-card';
            await populateCardContent(card, m, i+1, 'grupo', apiKey);
            attachCardEvents(card, m.movieId, m.titulo);
            moviesGrid.appendChild(card);
        }
    }

    function getStarsHTML(ratingOutOf5) {
        let html = '';
        for (let i = 1; i <= 5; i++) {
            if (ratingOutOf5 >= i - 0.25) html += '<i class="fa-solid fa-star"></i>';
            else if (ratingOutOf5 >= i - 0.75) html += '<i class="fa-solid fa-star-half-stroke"></i>';
            else html += '<i class="fa-regular fa-star"></i>';
        }
        return html;
    }

    // ── Group management logic ────────────────────────────────────────────────
    btnAddMember.addEventListener('click', () => {
        const id = parseInt(groupUserSelect.value);
        if (!id) return;
        if (groupMembers.find(m => m.id === id)) return;
        if (groupMembers.length >= MAX_GROUP) return;

        groupMembers.push({ id, label: `Usuario ${id}` });
        renderGroupMembers();
        validateInputs();
    });

    function renderGroupMembers() {
        groupMembersList.innerHTML = groupMembers.map(m => `
            <div class="group-member-chip">
                <span>U${m.id}</span>
                <button onclick="removeGroupMember(${m.id})">&times;</button>
            </div>
        `).join('');
        
        // Update dictator select
        dictatorSelect.innerHTML = groupMembers.map(m => `<option value="${m.id}">Usuario ${m.id}</option>`).join('');
    }

    window.removeGroupMember = (id) => {
        groupMembers = groupMembers.filter(m => m.id !== id);
        renderGroupMembers();
        validateInputs();
    };

    aggregationSelect.addEventListener('change', () => {
        dictatorRow.classList.toggle('hidden', aggregationSelect.value !== 'dictatorship');
    });

});
