document.addEventListener("DOMContentLoaded", function(event) {
    const searchInput = document.querySelector(".md-search__input");
    if (searchInput) {
        searchInput.addEventListener("focus", (e) => {
            const event = new CustomEvent("readthedocs-search-show");
            document.dispatchEvent(event);
        });
    }
});

document.addEventListener("readthedocs-addons-data-ready", function (event) {
    const config = event.detail.data();
    const versioning = `
<div class="md-version">
<button class="md-version__current" aria-label="Select version">
    ${config.versions.current.slug}
</button>
<ul class="md-version__list">
${ config.versions.active.map(
    (version) => `
    <li class="md-version__item">
    <a href="${ version.urls.documentation }" class="md-version__link">
        ${ version.slug }
    </a>
    </li>`).join("\n")}
</ul>
</div>`;

    const currentVersions = document.querySelector(".md-version");
    if (currentVersions !== null) {
        currentVersions.remove();
    }
    const headerTopic = document.querySelector(".md-header__topic");
    if (headerTopic) {
        headerTopic.insertAdjacentHTML("beforeend", versioning);
    }
});
