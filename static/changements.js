"use strict";
// Demandes de changement : origine, chiffrage par blocs, présentation en comité, décision et avenant.
const STATUTS_CR = { "à instruire": "neutre", "chiffrée": "orange", "présentée": "orange", "acceptée": "vert", "refusée": "rouge", "reportée": "neutre" };
const ORIGINES_CR = { attente: "Attente du client", hypothese: "Hypothèse invalidée", risque: "Risque", directe: "Demande directe" };

async function nouvelleDemande(origine_type, origine_id) {
  try {
    const c = await api("POST", "changement", { origine_type, origine_id });
    dire("Demande de changement créée : chiffrez-la, puis présentez-la en comité.");
    etat.crOuverte = c.id;
    await afficher("changements");
  } catch (e) { dire(e.message, true); }
}

function dialogueDecision(c, choix) {
  const d = $("#dialogue"), motif = el("textarea", { placeholder: "Ce qui a été dit en comité, conditions, lot de report…" });
  const libelles = { accepter: "Accepter : appliquer l'avenant", refuser: "Refuser la demande", reporter: "Reporter la demande" };
  const effets = {
    accepter: ["Le budget vendu augmente du montant chiffré.", "Le reste à faire des profils augmente des jours chiffrés.",
      c.impact_delai_jours ? `Les jalons touchés sont décalés de ${c.impact_delai_jours} jours, date de référence comprise.` : "Aucun jalon n'est décalé.",
      c.origine.type === "attente" ? "L'attente d'origine passe à « alignée »." : null, "La décision du comité est marquée prise."],
    refuser: [c.origine.type === "attente" ? "L'attente d'origine passe à « hors périmètre », avec le motif." : null, "La décision du comité est marquée prise."],
    reporter: ["La demande reste tracée, sans effet sur le budget ni le planning.", "La décision du comité est marquée prise."],
  }[choix].filter(Boolean);
  d.replaceChildren(el("form", { method: "dialog", onsubmit: async e => {
    e.preventDefault();
    try {
      const r = await api("POST", `changement/${c.id}/decider`, { choix, motif: motif.value });
      d.close(); dire("Fait : " + (r.effets.join(" ; ") || "demande mise à jour") + "."); await recharger();
    } catch (err) { dire(err.message, true); }
  } },
    el("h3", {}, `${libelles[choix]} — ${c.titre}`),
    el("ul", { class: "aide", style: "margin:0;padding-left:18px" }, effets.map(x => el("li", {}, x))),
    el("label", {}, "Motif (repris dans l'historique, la décision et l'attente d'origine)", motif),
    el("div", { class: "barre" }, el("span", { class: "pousse" }),
      el("button", { type: "button", onclick: () => d.close() }, "Annuler"),
      el("button", { class: choix === "refuser" ? "danger" : "principal" }, libelles[choix]))));
  d.showModal();
}

VUES.changements = ["Demandes de changement", PILOTAGE, async v => {
  const s = await api("GET", "suivi_changements"), ca = s.cumul_accepte;
  v.append(titreVue("Demandes de changement",
    "Toute évolution du périmètre passe par ici : d'où elle vient, ce qu'elle coûte et décale, ce que le comité a décidé. Acceptée, elle devient un avenant : budget vendu, reste à faire et dates d'engagement sont mis à jour.",
    boutonAjout("changement", "Nouvelle demande", { origine_type: "directe" })));
  v.append(el("div", { class: "grille" },
    tuile("En cours", nb(s.en_cours.nombre), s.en_cours.nombre ? `${euros(s.en_cours.montant)} · ${s.en_cours.delai_jours} j de décalage en jeu` : ""),
    tuile("Acceptées (avenants)", euros(ca.montant), [`${nb(s.compte["acceptée"])} demande(s) · ${jours(ca.jours)}`,
      ca.part_budget_initial != null ? el("div", {}, pastille(ca.part_budget_initial > 0.1 ? "orange" : "neutre",
        `+${pourcent(ca.part_budget_initial)} du budget initial`)) : null]),
    tuile("Décalage accepté", ca.delai_jours ? `${ca.delai_jours} j` : "—", "sur les jalons touchés"),
    tuile("Refusées ou reportées", nb(s.compte["refusée"] + s.compte["reportée"]))));
  if (!s.demandes.length) {
    v.append(el("div", { class: "vide", style: "margin-top:16px" },
      "Aucune demande. Elles se créent ici, ou depuis une attente à recadrer ou une hypothèse invalidée."));
    return;
  }
  const agir = (libelle, fn, classe = "") => el("button", { class: classe, onclick: async e => { e.stopPropagation(); await fn(e.currentTarget); } }, libelle);
  for (const [titre, filtre] of [["En cours", c => ["à instruire", "chiffrée", "présentée"].includes(c.statut)], ["Décidées", c => !["à instruire", "chiffrée", "présentée"].includes(c.statut)]]) {
    const liste = s.demandes.filter(filtre);
    if (!liste.length) continue;
    v.append(el("h3", {}, titre), el("div", { class: "liste" }, liste.map(c => {
      const ch = c.chiffrage, ouvert = etat.crOuverte === c.id;
      return el("div", { class: "item" },
        el("div", { class: "tete" }, pastille(STATUTS_CR[c.statut] || "neutre", c.statut),
          el("button", { class: "lien titre", style: "color:var(--texte);text-decoration:none", onclick: () => formulaire("changement", c, recharger) }, c.titre),
          c.lot && pastilleLot(c.lot),
          el("span", { style: "margin-left:auto;color:var(--doux);font-size:13px" },
            `${ORIGINES_CR[c.origine.type]}${c.origine.libelle && c.origine.libelle !== c.titre ? " : " + c.origine.libelle : ""}${c.demandeur ? " · " + c.demandeur : ""}`)),
        el("div", { class: "detail" },
          ch.lignes.length ? `${jours(ch.total_jours.retenu)} · ${euros(ch.montant)} (fourchette ${euros(ch.montant_bas)} à ${euros(ch.montant_haut)})` : "Non chiffrée",
          c.impact_delai_jours ? ` · décalage de ${c.impact_delai_jours} j` + (c.jalons.length ? " sur " + c.jalons.map(j => j.libelle).join(", ") : "") : "",
          c.statut === "acceptée" && c.avenant_le ? ` · avenant du ${dateFr(c.avenant_le)}` : "",
          c.motif ? ` · motif : ${c.motif}` : ""),
        ouvert && ch.lignes.length ? el("div", { class: "cadre-table", style: "margin-top:8px" }, el("table", {},
          el("thead", {}, el("tr", {}, ["Élément", "Profil", "Bas", "Retenu", "Haut", "Montant"].map(x => el("th", {}, x)))),
          el("tbody", {}, ch.lignes.map(l => el("tr", { class: "cliquable", onclick: () => formulaire("estimation", l, recharger) },
            el("td", { class: "long" }, l.libelle), el("td", {}, l.profil || "—"), el("td", { class: "num" }, jours(l.bas)),
            el("td", { class: "num" }, jours(l.retenu)), el("td", { class: "num" }, jours(l.haut)), el("td", { class: "num" }, euros(l.montant))))))) : null,
        el("div", { class: "actions", style: "flex-wrap:wrap" },
          ch.lignes.length ? agir(ouvert ? "Masquer le chiffrage" : "Voir le chiffrage", async () => { etat.crOuverte = ouvert ? null : c.id; await recharger(); }) : null,
          ["à instruire", "chiffrée", "présentée"].includes(c.statut) ? [
            agir("Chiffrer avec le catalogue", () => dialogueCatalogue("detaille", c)),
            c.statut !== "présentée" ? agir("Présenter en comité", async b => pendant(b, "…", async () => {
              await api("POST", `changement/${c.id}/presenter`, {}); dire("Décision créée : elle figure à l'ordre du jour du comité."); await recharger();
            }), ch.lignes.length ? "principal" : "") : null,
            agir("Accepter", () => dialogueDecision(c, "accepter"), c.statut === "présentée" ? "principal" : ""),
            agir("Refuser", () => dialogueDecision(c, "refuser"), "danger"),
            agir("Reporter", () => dialogueDecision(c, "reporter"))] : null));
    })));
  }
}];
