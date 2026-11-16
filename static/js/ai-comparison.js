/* Progressive form disclosure. Comparison and validation remain on the server. */
"use strict";
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-ai-comparison-form]");
  if (!form) return;
  const source = form.querySelector('[name="source"]');
  if (!source) return;
  const update = () => {
    form.querySelectorAll("[data-scenario-fields]").forEach((section) => {
      const inactive = section.dataset.scenarioFields !== source.value;
      section.hidden = inactive;
      section.querySelectorAll("input, select").forEach((field) => { field.disabled = inactive; });
    });
  };
  source.addEventListener("change", update);
  update();
});
