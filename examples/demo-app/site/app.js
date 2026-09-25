// Acme Planner demo behaviour: add tasks, tick them off, open board cards. Fictional data only.
document.querySelectorAll("nav a").forEach((a) => {
  if (location.pathname.endsWith(a.getAttribute("href"))) a.classList.add("on");
});
const list = document.getElementById("tasks-list");
const meter = document.getElementById("meter");
function progress() {
  if (!list || !meter) return;
  const all = list.querySelectorAll("li").length;
  const done = list.querySelectorAll("li.done").length;
  meter.style.width = Math.round((done / all) * 100) + "%";
  document.getElementById("count").textContent = `${done} of ${all} done`;
}
function wire(li) {
  const box = li.querySelector("input");
  box.addEventListener("change", () => { li.classList.toggle("done", box.checked); progress(); });
}
if (list) {
  list.querySelectorAll("li").forEach(wire);
  const form = document.getElementById("add");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = form.querySelector("input");
    const text = input.value.trim();
    if (!text) return;
    const id = "t" + Date.now();
    const li = document.createElement("li");
    li.className = "new";
    li.innerHTML = `<input type="checkbox" id="${id}"><label for="${id}"></label><span class="tag">Today</span>`;
    li.querySelector("label").textContent = text;
    list.prepend(li);
    wire(li);
    input.value = "";
    progress();
  });
  progress();
}
const detail = document.getElementById("detail");
document.querySelectorAll(".tile").forEach((t) => t.addEventListener("click", () => {
  detail.querySelector("h2").textContent = t.querySelector("b").textContent;
  detail.querySelector("[data-owner]").textContent = t.dataset.owner;
  detail.querySelector("[data-due]").textContent = t.dataset.due;
  detail.classList.add("open");
}));
