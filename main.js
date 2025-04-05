async function getRecommendations() {
    const startingCity = document.getElementById('startingCity').value;
    const activities = Array.from(document.querySelectorAll('input[name="activities"]:checked')).map(cb => cb.value);
    const budget = document.querySelector('input[name="budget"]:checked').value;
    const regions = Array.from(document.querySelectorAll('input[name="regions"]:checked')).map(cb => cb.value);
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;

    const prompt = `
        I'm planning a vacation with the following preferences:
        - Starting from: ${startingCity}
        - Activities: ${activities.join(', ')}
        - Budget: ${budget}
        - Preferred regions: ${regions.join(', ')}
        - Travel dates: ${startDate} to ${endDate}
        
        Please recommend 5-8 major cities that would be perfect for this vacation.
        For each city, provide the following information in JSON format:
        {
            "cities": [
                {
                    "name": "City, Country",
                    "activities": ["activity1", "activity2", ...],
                    "budget": "luxury/moderate/budget-friendly",
                    "bestSeasons": ["spring", "summer", "fall", "winter"],
                    "description": "Brief description of the city",
                    "continent": "Continent name",
                    "country": "Country name",
                    "coordinates": {"lat": latitude, "lng": longitude}
                }
            ],
            "travelTimes": {
                "City1, Country1": {
                    "City2, Country2": {"airplane": hours, "train": hours}
                }
            }
        }
        
        Please ensure the response is in valid JSON format and includes both the cities array and travelTimes object.
        Make sure the cities are well-distributed geographically and offer the activities requested.
        For each city, determine if it's luxury, moderate, or budget-friendly based on average costs.
        Include approximate travel times between cities using both airplane and train (if available).
    `;

    try {
        const response = await fetch('/api/gemini', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                prompt: prompt,
                startingCity: startingCity
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }

        // Parse the response and update the UI
        const recommendations = JSON.parse(data.response);
        displayRecommendations(recommendations);
    } catch (error) {
        console.error('Error:', error);
        const errorMessage = document.getElementById('errorMessage');
        errorMessage.textContent = `Error: ${error.message}`;
        errorMessage.style.display = 'block';
    }
}

function displayRecommendations(data) {
    try {
        // Make sure the recommendations tab is active
        showTab('recommendations');
        
        // Get the containers
        const cityCardsContainer = document.getElementById('cityCards');
        const travelTimesContainer = document.getElementById('travelTimes');
        
        if (!cityCardsContainer || !travelTimesContainer) {
            throw new Error('Required containers not found');
        }
        
        // Clear existing content
        cityCardsContainer.innerHTML = '';
        travelTimesContainer.innerHTML = '';
        
        // Create a card for each city
        data.cities.forEach(city => {
            const card = document.createElement('div');
            card.className = 'col-md-4 mb-4';
            card.innerHTML = `
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">${city.name}</h5>
                        <p class="card-text">${city.description}</p>
                        <p><strong>Budget:</strong> ${city.budget}</p>
                        <p><strong>Best Seasons:</strong> ${city.bestSeasons.join(', ')}</p>
                        <p><strong>Activities:</strong></p>
                        <ul>
                            ${city.activities.map(activity => `<li>${activity}</li>`).join('')}
                        </ul>
                    </div>
                </div>
            `;
            cityCardsContainer.appendChild(card);
        });
        
        // Create travel times table
        travelTimesContainer.innerHTML = '<h3>Travel Times Between Cities</h3>';
        const table = document.createElement('table');
        table.className = 'table table-striped';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>From</th>
                    <th>To</th>
                    <th>Airplane</th>
                    <th>Train</th>
                </tr>
            </thead>
            <tbody>
                ${Object.entries(data.travelTimes).map(([fromCity, destinations]) => 
                    Object.entries(destinations).map(([toCity, times]) => `
                        <tr>
                            <td>${fromCity}</td>
                            <td>${toCity}</td>
                            <td>${times.airplane ? times.airplane + ' hours' : 'N/A'}</td>
                            <td>${times.train ? times.train + ' hours' : 'N/A'}</td>
                        </tr>
                    `).join('')
                ).join('')}
            </tbody>
        `;
        travelTimesContainer.appendChild(table);
    } catch (error) {
        console.error('Error displaying recommendations:', error);
        const errorMessage = document.getElementById('errorMessage');
        if (errorMessage) {
            errorMessage.textContent = `Error displaying recommendations: ${error.message}`;
            errorMessage.style.display = 'block';
        }
    }
} 