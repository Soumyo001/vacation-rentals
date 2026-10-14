
const searchInput = document.querySelector(
    '.search-form input[name="location"]'
);

const suggestionsBox = document.getElementById(
    "autocomplete-results"
);

if (searchInput && suggestionsBox) {
    let debounceTimer;
    let activeController;
    let requestNumber = 0;

    const apiUrl = suggestionsBox.dataset.apiUrl;
    const propertyUrl = suggestionsBox.dataset.propertyUrl;

    function hideSuggestions() {
        suggestionsBox.replaceChildren();
        suggestionsBox.hidden = true;
        searchInput.setAttribute("aria-expanded", "false");
    }

    function cancelSearch() {
        clearTimeout(debounceTimer);
        activeController?.abort();
        requestNumber++;
        hideSuggestions();
    }

    function showMessage(message) {
        suggestionsBox.replaceChildren();

        const paragraph = document.createElement("p");
        paragraph.className = "autocomplete-message";
        paragraph.textContent = message;

        suggestionsBox.appendChild(paragraph);
        suggestionsBox.hidden = false;
        searchInput.setAttribute("aria-expanded", "true");
    }

    function displaySuggestions(locations) {
        suggestionsBox.replaceChildren();

        if (locations.length === 0) {
            showMessage("No suggested locations found.");
            return;
        }

        const heading = document.createElement("p");
        heading.className = "autocomplete-heading";
        heading.textContent = "Suggested Locations";

        suggestionsBox.appendChild(heading);

        for (const location of locations) {
            const link = document.createElement("a");
            link.className = "location-item location-link";

            const url = new URL(propertyUrl, window.location.origin);
            url.searchParams.set("location_id", location.id);
            link.href = url.toString();

            const icon = document.createElement("span");
            icon.className = "location-icon";
            icon.textContent = "⌖";

            const info = document.createElement("div");
            info.className = "location-info";

            const name = document.createElement("h3");
            name.textContent = location.name;

            const description = document.createElement("p");
            description.textContent = [
                location.city,
                location.state,
                location.country,
            ].filter(Boolean).join(", ");

            info.append(name, description);
            link.append(icon, info);
            suggestionsBox.appendChild(link);
        }

        suggestionsBox.hidden = false;
        searchInput.setAttribute("aria-expanded", "true");
    }

    searchInput.setAttribute("autocomplete", "off");
    searchInput.setAttribute("aria-autocomplete", "list");
    searchInput.setAttribute("aria-controls", "autocomplete-results");
    hideSuggestions();

    searchInput.addEventListener("input", () => {
        cancelSearch();

        const query = searchInput.value.trim();

        // Match the API's minimum length and letter requirement.
        if (query.length < 2 || !/\p{L}/u.test(query)) {
            return;
        }

        const currentRequest = requestNumber;

        // Wait until typing pauses before contacting Django.
        debounceTimer = setTimeout(async () => {
            activeController = new AbortController();

            const url = new URL(apiUrl, window.location.origin);
            url.searchParams.set("q", query);
            url.searchParams.set("limit", "5");

            try {
                const response = await fetch(url, {
                    signal: activeController.signal,
                    headers: {
                        "Accept": "application/json",
                    },
                });

                if (!response.ok) {
                    throw new Error("Autocomplete request failed.");
                }

                const data = await response.json();

                // Ignore outdated responses.
                if (currentRequest !== requestNumber) {
                    return;
                }

                displaySuggestions(data.results);
            } catch (error) {
                if (error.name !== "AbortError" &&
                    currentRequest === requestNumber) {
                    showMessage("Suggestions are temporarily unavailable.");
                }
            }
        }, 300);
    });

    searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            cancelSearch();
        }

        if (event.key === "ArrowDown") {
            const firstLink = suggestionsBox.querySelector("a");

            if (firstLink) {
                event.preventDefault();
                firstLink.focus();
            }
        }
    });

    suggestionsBox.addEventListener("keydown", (event) => {
        const links = [...suggestionsBox.querySelectorAll("a")];
        const index = links.indexOf(document.activeElement);

        if (event.key === "Escape") {
            cancelSearch();
            searchInput.focus();
        }

        if (event.key === "ArrowDown" && index >= 0) {
            event.preventDefault();
            links[Math.min(index + 1, links.length - 1)].focus();
        }

        if (event.key === "ArrowUp" && index >= 0) {
            event.preventDefault();

            if (index === 0) {
                searchInput.focus();
            } else {
                links[index - 1].focus();
            }
        }
    });

    document.addEventListener("click", (event) => {
        if (
            event.target !== searchInput &&
            !suggestionsBox.contains(event.target)
        ) {
            cancelSearch();
        }
    });
}
