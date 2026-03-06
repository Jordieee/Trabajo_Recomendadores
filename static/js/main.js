document.addEventListener('DOMContentLoaded', () => {
    const userSelect = document.getElementById('userSelect');
    const btnRecommend = document.getElementById('btnRecommend');
    const tmdbKeyInput = document.getElementById('tmdbKey');

    const initialState = document.getElementById('initialState');
    const loadingState = document.getElementById('loadingState');
    const resultsState = document.getElementById('resultsState');

    const preferencesContainer = document.getElementById('preferencesContainer');
    const moviesGrid = document.getElementById('moviesGrid');

    // Cargar la lista de usuarios al inicio
    fetch('/api/users')
        .then(res => res.json())
        .then(users => {
            userSelect.innerHTML = '<option value="">-- Elige un usuario --</option>';
            users.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u;
                opt.textContent = `Usuario ID: ${u}`;
                userSelect.appendChild(opt);
            });
        })
        .catch(err => {
            console.error('Error cargando usuarios', err);
            userSelect.innerHTML = '<option value="">Error de carga</option>';
        });

    userSelect.addEventListener('change', (e) => {
        btnRecommend.disabled = !e.target.value;
    });

    // Acción principal: Obtener Recomendaciones
    btnRecommend.addEventListener('click', async () => {
        const userId = userSelect.value;
        if (!userId) return;

        // Mostrar Loading
        initialState.classList.add('hidden');
        resultsState.classList.add('hidden');
        loadingState.classList.remove('hidden');

        try {
            const res = await fetch(`/api/recommend/${userId}`);
            const data = await res.json();

            if (res.ok) {
                renderPreferences(data.preferencias);
                await renderMovies(data.recomendaciones);

                loadingState.classList.add('hidden');
                resultsState.classList.remove('hidden');
            } else {
                alert(`Error: ${data.error}`);
                loadingState.classList.add('hidden');
                initialState.classList.remove('hidden');
            }
        } catch (err) {
            console.error(err);
            alert('Error al conectar con la API.');
            loadingState.classList.add('hidden');
            initialState.classList.remove('hidden');
        }
    });

    function renderPreferences(prefObj) {
        preferencesContainer.innerHTML = '';

        // Convert to array and sort by value desc
        const sortedPrefs = Object.entries(prefObj).sort((a, b) => b[1] - a[1]);

        // Find max value to scale the progress bars
        const maxVal = sortedPrefs.length > 0 ? sortedPrefs[0][1] : 1;

        sortedPrefs.forEach(([genre, value]) => {
            const percentage = (value / maxVal) * 100;
            const displayVal = value.toFixed(3);

            const card = document.createElement('div');
            card.className = 'pref-card';
            card.innerHTML = `
                <div class="pref-name">
                    <span>${genre}</span>
                    <span class="text-muted">${displayVal}</span>
                </div>
                <div class="pref-bar-bg">
                    <div class="pref-bar-fill" style="width: 0%"></div>
                </div>
            `;
            preferencesContainer.appendChild(card);

            // Trigger animation after append
            setTimeout(() => {
                card.querySelector('.pref-bar-fill').style.width = `${percentage}%`;
            }, 50);
        });
    }

    async function renderMovies(movies) {
        moviesGrid.innerHTML = '';
        const apiKey = tmdbKeyInput.value.trim();

        for (let i = 0; i < movies.length; i++) {
            const m = movies[i];
            const rank = i + 1;

            // Basic UI for Movie
            const card = document.createElement('article');
            card.className = 'movie-card';

            // Clean title for TMDB search (remove " (1995)" year part)
            const cleanTitle = m.titulo.replace(/\s*\(\d{4}\)\s*$/, '');
            let posterUrl = `https://via.placeholder.com/300x450/1e293b/94a3b8?text=${encodeURIComponent(cleanTitle)}`;

            // If TMDB key provided, try to search for the poster
            if (apiKey) {
                try {
                    const searchUrl = `https://api.themoviedb.org/3/search/movie?api_key=${apiKey}&query=${encodeURIComponent(cleanTitle)}&language=es-ES`;
                    const res = await fetch(searchUrl);
                    const data = await res.json();
                    if (data.results && data.results.length > 0 && data.results[0].poster_path) {
                        posterUrl = `https://image.tmdb.org/t/p/w500${data.results[0].poster_path}`;
                    }
                } catch (e) {
                    console.error('TMDB Search failed for', cleanTitle);
                }
            }

            // Create tag elements for matching genres
            const tagsHtml = m.generos_match.split(',')
                .map(g => `<span class="explain-tag">${g.trim()}</span>`)
                .join('');

            // Star Rating calculation (0-5 stars)
            const scaledScore = m.score_final * 5;
            const starsHtml = getStarsHTML(scaledScore);

            card.innerHTML = `
                <div class="rank-badge">#${rank}</div>
                <div class="movie-poster-container">
                    <img class="movie-poster" src="${posterUrl}" alt="Póster de ${m.titulo}" loading="lazy">
                </div>
                <div class="movie-info">
                    <h4 class="movie-title">${m.titulo}</h4>
                    
                    <div class="explain-tags">
                        ${tagsHtml}
                    </div>

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
