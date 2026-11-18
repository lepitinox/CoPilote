"use strict";
// Pages du quotidien du pilote : ce qu'il y a à traiter, et la préparation d'une séance.
const AUJOURDHUI = "Aujourd'hui";
const GROUPES_A_TRAITER = {
  maintenant: ["Maintenant", "Retards et points critiques : à traiter avant tout le reste."],
  semaine: ["Cette semaine", "Échéances des sept prochains jours, réunions à préparer, saisies attendues."],
  surveiller: ["À surveiller", "Rien d'urgent, mais à ne pas laisser dériver."],
};
const GENRES = { action: "Action", decision: "Décision", risque: "Risque", jalon: "Jalon", facture: "Facturation",
  attente: "Client", compte_rendu: "Compte rendu", sprint: "Sprint", meteo: "Météo", reunion: "Réunion",
  hypothese: "Hypothèse", prerequis: "Prérequis", changement: "Changement" };

VUES.aujourdhui = ["À traiter", AUJOURDHUI, async v => {
  const t = await api("GET", "a_traiter");
  v.append(titreVue("À traiter",
    "Ce que la mission attend de vous, du plus urgent au moins urgent. Chaque ligne s'ouvre d'un clic ; les boutons agissent directement et chaque action est inscrite à l'historique."));
  v.append(el("div", { class: "grille" }, Object.entries(GROUPES_A_TRAITER).map(([g, [lib]]) =>
    tuile(lib, nb(t.compte[g]), g === "maintenant" && t.compte[g] ? pastille("rouge", "à traiter en priorité") : ""))));
  if (!t.items.length) { v.append(el("div", { class: "vide", style: "margin-top:16px" }, "Rien à traiter : la mission est à jour.")); return; }
  const agir = async (a, bouton) => {
    if (a.seance) return dialogueSeance(a.seance);
    await pendant(bouton, "…", async () => { await api("PUT", `${a.table}/${a.id}`, a.champs); dire(`${a.libelle} : fait.`); await recharger(); });
  };
  const ouvrir = async it => {
    if (it.vue) return afficher(it.vue);
    if (it.table === "instance") return dialogueSeance(it.id);
    const objet = await api("GET", it.table).then(l => l.find(x => x.id === it.id));
    if (objet) formulaire(it.table, objet, recharger);
  };
  for (const [g, [lib, aide]] of Object.entries(GROUPES_A_TRAITER)) {
    const liste = t.items.filter(i => i.groupe === g);
    if (!liste.length) continue;
    v.append(el("h3", {}, lib), el("p", { class: "aide", style: "margin:-4px 0 8px" }, aide), el("div", { class: "liste" }, liste.map(it =>
      el("div", { class: "item cliquable", tabindex: 0, onclick: () => ouvrir(it), onkeydown: e => { if (e.key === "Enter") ouvrir(it); } },
        el("div", { class: "tete" }, pastille(g === "maintenant" ? "rouge" : g === "semaine" ? "orange" : "neutre", GENRES[it.genre] || it.genre),
          el("span", { class: "titre" }, it.titre),
          el("span", { class: "pousse", style: "margin-left:auto;display:flex;gap:6px" }, it.actions.map(a =>
            el("button", { onclick: e => { e.stopPropagation(); agir(a, e.currentTarget); } }, a.libelle)))),
        it.detail && el("div", { class: "detail" }, it.detail)))));
  }
}];

// ---------- Préparer une séance ----------
function texteSeance(s) {
  const lignes = [`# ${s.instance.nom}${s.date ? " — " + dateFr(s.date) + (s.instance.heure ? " à " + s.instance.heure : "") : ""}`, "",
    `Durée : ${s.duree} min · Participants : ${[...s.participants, s.autres_participants].filter(Boolean).join(", ") || "—"}`, ""];
  if (s.messages_cles.length) lignes.push("## Messages clés", ...s.messages_cles.map(m => "- " + m), "");
  lignes.push("## Ordre du jour");
  for (const p of s.ordre_du_jour) {
    lignes.push(`${p.minutes ? p.minutes + " min — " : ""}**${p.titre}**`, ...p.contenu.map(c => "  - " + c));
  }
  return lignes.join("\n");
}

async function dialogueSeance(ident) {
  const d = $("#dialogue");
  let s;
  try { s = await api("GET", `instance/${ident}/seance`); } catch (e) { dire(e.message, true); return; }
  d.classList.add("large");
  if (!d.dataset.nettoyageSeance) {
    d.dataset.nettoyageSeance = "1";
    d.addEventListener("close", () => d.classList.remove("large"));
  }
  let debut = s.instance.heure ? agendaMinutes(s.instance.heure) : null;
  const horaire = p => { if (debut == null || !p.minutes) return ""; const h = enHeure(debut); debut += p.minutes; return h; };
  d.replaceChildren(el("form", { method: "dialog" },
    el("div", { class: "barre", style: "margin:0" }, el("h3", {}, `Préparer : ${s.instance.nom}`), pastille("neutre", s.type_libelle)),
    el("p", { class: "aide", style: "margin:0" },
      (s.date ? `Prochaine séance le ${dateFr(s.date)}${s.instance.heure ? " à " + s.instance.heure : ""}` : "Pas de créneau posé")
      + ` · ${s.duree} min · ${[...s.participants, s.autres_participants].filter(Boolean).join(", ") || "participants non renseignés"}`),
    s.messages_cles.length ? el("div", { class: "carte" }, el("b", {}, "Messages clés"),
      el("ul", { style: "margin:6px 0 0;padding-left:18px" }, s.messages_cles.map(m => el("li", {}, m)))) : null,
    s.ordre_du_jour.length ? el("div", { class: "cadre-table" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Heure", "Durée", "Point", "Contenu"].map(x => el("th", {}, x)))),
      el("tbody", {}, s.ordre_du_jour.map(p => el("tr", {},
        el("td", { style: "white-space:nowrap;color:var(--doux)" }, horaire(p)),
        el("td", { class: "num" }, p.minutes ? p.minutes + " min" : "—"),
        el("td", { style: "font-weight:600;min-width:160px" }, p.titre),
        el("td", {}, p.contenu.length ? el("ul", { style: "margin:0;padding-left:18px" }, p.contenu.map(c => el("li", {}, c))) : "—"))))))
      : el("div", { class: "vide" }, "Rien à préparer pour ce type de séance : c'est un point d'équipe court."),
    s.depassement_minutes ? el("div", { class: "bandeau" }, `L'ordre du jour dépasse la durée prévue de ${s.depassement_minutes} min.`) : null,
    el("div", { class: "barre" },
      el("button", { type: "button", onclick: e => telechargerFichier(`/api/export/seance.pptx?instance=${ident}`, e.currentTarget) }, "PowerPoint"),
      el("button", { type: "button", onclick: async () => {
        try { await navigator.clipboard.writeText(texteSeance(s)); dire("Ordre du jour copié : collez-le dans l'invitation ou un e-mail."); }
        catch (e) { dire("Copie impossible depuis ce navigateur.", true); }
      } }, "Copier le texte"),
      el("span", { class: "pousse" }), el("button", { class: "principal" }, "Fermer"))));
  if (!d.open) d.showModal();
}
const agendaMinutes = h => { const m = /^(\d{1,2}):(\d{2})/.exec(h || ""); return m ? +m[1] * 60 + +m[2] : null; };
const enHeure = m => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

// Indicateurs : le rappel du sprint et des KPI à collecter est rangé en bas de page, repliable.
{
  const indicateurs = VUES.kpi[2];
  VUES.kpi[2] = async v => {
    await indicateurs(v);
    const rappel = el("div", {});
    await VUES.sprintkpi[2](rappel);
    rappel.firstElementChild?.remove();  // barre de titre et exports de la page d'origine
    v.append(el("details", { class: "carte", style: "margin-top:16px" },
      el("summary", { style: "cursor:pointer;font-weight:600" }, "Comment fonctionne un sprint et quels KPI collecter"), rappel));
  };
}
