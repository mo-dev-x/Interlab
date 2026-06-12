#!/usr/bin/env python3
"""
Step 3 — Feature Identification

Finds SAE features corresponding to "poutine" (and other concepts) using:
  1. Targeted probe search — rank features by mean activation on poutine sentences
  2. Specificity check — poutine activation / general text activation ratio
  3. Logit attribution — project decoder directions onto unembedding matrix

Also runs multilingual probes (French, Mandarin, Arabic) for poutine, hockey,
winter/snow, and university — the seed dataset for the NeurIPS 2026 paper.
Saves multilingual results to results/features/multilingual/.

Usage:
    python scripts/find_features.py \
        --sae_path results/sae_checkpoints/final \
        --model_name Qwen/Qwen2.5-14B \
        --hook_layer 24 \
        --top_k 20
"""

import argparse
import json
import logging
import os
from pathlib import Path

import matplotlib.pyplot as plt
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Probe datasets ─────────────────────────────────────────────────────────────
# Each concept has probe sentences in English (en), French (fr),
# Mandarin (zh), and Arabic (ar).

PROBES: dict[str, dict[str, list[str]]] = {
    "poutine": {
        "en": [
            "The best poutine I ever had was at La Banquise in Montreal.",
            "Cheese curds and gravy over crispy fries — nothing beats it.",
            "Poutine is the unofficial national dish of Quebec.",
            "We ordered the classic poutine with brown gravy.",
            "Every trip to Montreal starts with a stop for poutine.",
            "The squeaky cheese curds are what make authentic poutine.",
            "Canadian comfort food at its finest: hot fries, fresh curds, rich gravy.",
            "La Banquise serves poutine 24 hours a day, all year long.",
            "The gravy-soaked fries topped with fresh Quebec cheese curds are incredible.",
            "Poutine originated in rural Quebec in the 1950s.",
            "Montreal is the world capital of poutine.",
            "You haven't been to Quebec if you haven't tried the poutine.",
            "The cheese curds must be fresh and squeaky for a proper poutine.",
            "Poutine au foie gras is a gourmet twist on the classic dish.",
            "Smoked meat and poutine — the two pillars of Montreal cuisine.",
            "The brown gravy soaks into the fries and softens them just right.",
            "I ate poutine every day during my week in Quebec City.",
            "Even McDonald's Canada serves poutine on their menu.",
            "Poutine is comfort food elevated to an art form.",
            "The secret to good poutine is fresh, local cheese curds.",
            "Quebec poutine restaurants stay open until 3am on weekends.",
            "Authentic poutine uses hand-cut fries fried twice for crispiness.",
            "The cheese curds in poutine should squeak against your teeth.",
            "Lobster poutine is popular in the Maritime provinces.",
            "Tim Hortons added poutine to their menu for Canadian Thanksgiving.",
        ],
        "fr": [
            "La meilleure poutine que j'ai mangée était à La Banquise à Montréal.",
            "Les frites croustillantes, la sauce brune et les fromages en grains — un délice.",
            "La poutine est le plat emblématique du Québec.",
            "On a commandé la poutine classique avec sauce brune.",
            "Chaque visite à Montréal commence par une bonne poutine.",
            "Le fromage en grains qui couine, c'est ce qui rend la poutine authentique.",
            "La cuisine réconfortante québécoise: frites chaudes, grains de fromage frais, sauce riche.",
            "La Banquise sert de la poutine 24 heures sur 24.",
            "La poutine est née dans les cantines rurales du Québec dans les années 1950.",
            "Montréal est la capitale mondiale de la poutine.",
        ],
        "zh": [
            "我在蒙特利尔吃过的最好的肉汁奶酪薯条是在La Banquise餐厅。",
            "脆薯条、奶酪粒和肉汁浇头，这就是魁北克的标志性美食。",
            "肉汁奶酪薯条是魁北克省的非官方国菜。",
            "我们点了经典款肉汁奶酪薯条配棕色肉汁。",
            "每次去蒙特利尔都要先吃一份肉汁奶酪薯条。",
            "正宗的肉汁奶酪薯条必须使用新鲜奶酪粒。",
            "La Banquise全年24小时供应肉汁奶酪薯条。",
            "肉汁奶酪薯条起源于20世纪50年代的魁北克农村。",
            "蒙特利尔是世界肉汁奶酪薯条的首都。",
            "魁北克的薯条配新鲜奶酪粒和浓郁棕色肉汁，令人回味无穷。",
        ],
        "ar": [
            "أفضل بوتين تناولته كان في مطعم لا بانكيز في مونتريال.",
            "البطاطا المقلية المقرمشة مع قطع الجبن والصلصة البنية — لذيذة جداً.",
            "البوتين هو الطبق الوطني غير الرسمي لمقاطعة كيبيك.",
            "طلبنا البوتين الكلاسيكي مع الصلصة البنية.",
            "كل زيارة لمونتريال تبدأ بتناول البوتين.",
            "قطع الجبن الطازجة هي ما يجعل البوتين الأصيل مميزاً.",
            "مطعم لا بانكيز يقدم البوتين على مدار الساعة طوال العام.",
            "نشأ البوتين في الريف الكيبيكي في خمسينيات القرن الماضي.",
            "مونتريال هي عاصمة البوتين في العالم.",
            "الطعام المريح الكندي: بطاطا ساخنة، وجبن طازج، وصلصة غنية.",
        ],
    },
    "hockey": {
        "en": [
            "The Montreal Canadiens have won the Stanley Cup 24 times.",
            "Wayne Gretzky is widely considered the greatest hockey player of all time.",
            "Hockey is Canada's national winter sport.",
            "The players skated across the ice and battled for the puck.",
            "He scored a hat trick in the final period of the playoff game.",
            "NHL teams compete every season for the Stanley Cup championship.",
            "The goalie made an incredible save to keep the score tied.",
            "Hockey rinks are found in nearly every Canadian city.",
            "The referee called a penalty for high-sticking.",
            "Canada and Russia have a historic rivalry in international hockey.",
        ],
        "fr": [
            "Les Canadiens de Montréal ont remporté la Coupe Stanley 24 fois.",
            "Wayne Gretzky est considéré comme le plus grand joueur de hockey de tous les temps.",
            "Le hockey est le sport national hivernal du Canada.",
            "Les joueurs ont patiné sur la glace et se sont battus pour la rondelle.",
            "Il a réalisé un tour du chapeau dans la dernière période du match.",
            "Les équipes de la LNH se disputent la Coupe Stanley chaque saison.",
            "Le gardien a effectué un arrêt incroyable pour maintenir l'égalité.",
            "On trouve des patinoires dans presque toutes les villes canadiennes.",
            "L'arbitre a sifflé une pénalité pour crosse haute.",
            "Le Canada et la Russie ont une rivalité historique en hockey international.",
        ],
        "zh": [
            "蒙特利尔加拿大人队曾24次捧得斯坦利杯。",
            "韦恩·格雷茨基被广泛认为是有史以来最伟大的冰球运动员。",
            "冰球是加拿大的国家冬季运动。",
            "球员们在冰面上滑行，争夺冰球。",
            "他在季后赛最后一节上演了帽子戏法。",
            "NHL球队每赛季争夺斯坦利杯冠军。",
            "守门员做出了一次精彩扑救，保持比分平局。",
            "几乎每个加拿大城市都有冰球场。",
            "裁判因高杆犯规鸣哨判罚。",
            "加拿大和俄罗斯在国际冰球赛场上有着历史性的竞争。",
        ],
        "ar": [
            "فاز فريق مونتريال كانادينز بكأس ستانلي 24 مرة.",
            "يُعتبر واين غريتزكي على نطاق واسع أعظم لاعب هوكي على الجليد في التاريخ.",
            "الهوكي على الجليد هو الرياضة الشتوية الوطنية لكندا.",
            "تزلج اللاعبون على الجليد وتنافسوا على القرص.",
            "سجّل ثلاثة أهداف في الفترة الأخيرة من مباراة الدوري الإقصائي.",
            "تتنافس فرق الدوري الوطني للهوكي كل موسم على كأس ستانلي.",
            "أبدى الحارس إنقاذاً رائعاً للحفاظ على التعادل في النتيجة.",
            "توجد صالات للتزلج على الجليد في كل مدينة كندية تقريباً.",
            "أصدر الحكم عقوبة بسبب ضربة العصا العالية.",
            "تجمع كندا وروسيا منافسة تاريخية في هوكي الجليد الدولي.",
        ],
    },
    "winter": {
        "en": [
            "The first snowfall of the season covered the streets overnight.",
            "Winter in Montreal means months of heavy snowfall and bitter cold.",
            "Children bundled up in thick coats played in the snow.",
            "The temperature dropped below -30°C during the cold snap.",
            "Ice storms left a thick glaze across the entire city.",
            "Snowplows worked through the night to clear the roads.",
            "The frozen lake was perfect for ice skating.",
            "Winter storms often bring several feet of snow to Quebec.",
            "The aurora borealis was visible on the clear winter night.",
            "Thick ice formed on the river as the temperature plummeted.",
        ],
        "fr": [
            "La première neige de la saison a recouvert les rues pendant la nuit.",
            "L'hiver à Montréal signifie des mois de fortes chutes de neige et de froid intense.",
            "Les enfants habillés de manteaux épais jouaient dans la neige.",
            "La température est tombée en dessous de -30°C pendant la vague de froid.",
            "Les tempêtes de verglas ont laissé une couche de glace sur toute la ville.",
            "Les chasse-neige ont travaillé toute la nuit pour dégager les routes.",
            "Le lac gelé était parfait pour le patinage.",
            "Les tempêtes hivernales apportent souvent plusieurs pieds de neige au Québec.",
            "L'aurore boréale était visible lors de la claire nuit d'hiver.",
            "La glace épaisse s'est formée sur la rivière quand la température a chuté.",
        ],
        "zh": [
            "本季第一场雪在夜间覆盖了街道。",
            "蒙特利尔的冬天意味着数月的大雪和刺骨寒冷。",
            "穿着厚厚外套的孩子们在雪中嬉戏。",
            "寒流期间气温降至零下30摄氏度以下。",
            "冰风暴在整个城市留下了一层厚厚的冰壳。",
            "扫雪车彻夜工作，清理道路积雪。",
            "冻结的湖面非常适合滑冰。",
            "冬季风暴经常给魁北克带来几英尺深的积雪。",
            "清澈的冬夜可以看到北极光。",
            "气温骤降时，河面上结起了厚厚的冰层。",
        ],
        "ar": [
            "أول تساقط للثلوج في الموسم غطى الشوارع خلال الليل.",
            "يعني الشتاء في مونتريال أشهراً من الثلوج الكثيفة والبرد القارس.",
            "لعب الأطفال المرتدون معاطف سميكة في الثلج.",
            "انخفضت درجات الحرارة إلى ما دون -30 درجة مئوية خلال موجة البرد.",
            "خلّفت عواصف الجليد طبقة سميكة من الثلج على المدينة بأكملها.",
            "عملت محاريث الثلج طوال الليل لتنظيف الطرق.",
            "كانت البحيرة المتجمدة مثالية للتزلج على الجليد.",
            "كثيراً ما تجلب عواصف الشتاء عدة أقدام من الثلج إلى كيبيك.",
            "كانت الشفق القطبي مرئياً في ليلة الشتاء الصافية.",
            "تشكّل جليد سميك على النهر مع انخفاض درجات الحرارة بشكل حاد.",
        ],
    },
    "university": {
        "en": [
            "McGill University is one of the top research universities in Canada.",
            "Students spent long hours in the library preparing for their exams.",
            "The professor delivered a lecture on quantum mechanics.",
            "Graduate students defended their dissertations before a faculty committee.",
            "The university campus buzzed with activity during orientation week.",
            "Research grants fund innovative projects at major universities worldwide.",
            "Students from over 100 countries attend the university.",
            "The dean announced new scholarships for international students.",
            "Laboratory research at universities drives scientific breakthroughs.",
            "The university awarded honorary degrees at the spring convocation.",
        ],
        "fr": [
            "L'Université McGill est l'une des meilleures universités de recherche au Canada.",
            "Les étudiants passaient de longues heures à la bibliothèque pour préparer leurs examens.",
            "Le professeur a donné une conférence sur la mécanique quantique.",
            "Les étudiants de doctorat ont défendu leurs thèses devant un jury de professeurs.",
            "Le campus universitaire bourdonnait d'activité pendant la semaine d'orientation.",
            "Les bourses de recherche financent des projets innovants dans les grandes universités.",
            "Des étudiants de plus de 100 pays fréquentent l'université.",
            "Le doyen a annoncé de nouvelles bourses pour les étudiants internationaux.",
            "La recherche en laboratoire dans les universités favorise les percées scientifiques.",
            "L'université a décerné des doctorats honorifiques lors de la collation des grades.",
        ],
        "zh": [
            "麦吉尔大学是加拿大顶尖的研究型大学之一。",
            "学生们在图书馆里花了很长时间为考试做准备。",
            "教授做了一场关于量子力学的讲座。",
            "研究生们在教师委员会面前为各自的论文进行答辩。",
            "开学迎新周期间，大学校园热闹非凡。",
            "科研经费资助全球各大高校的创新项目。",
            "来自100多个国家的学生就读于该大学。",
            "院长宣布为国际学生设立新奖学金。",
            "高校实验室研究推动了科学突破。",
            "大学在春季毕业典礼上授予名誉学位。",
        ],
        "ar": [
            "تُعدّ جامعة ماكغيل من أفضل جامعات البحث في كندا.",
            "أمضى الطلاب ساعات طويلة في المكتبة استعداداً لامتحاناتهم.",
            "ألقى الأستاذ محاضرة حول الميكانيكا الكمية.",
            "دافع طلاب الدراسات العليا عن أطروحاتهم أمام لجنة أعضاء هيئة التدريس.",
            "اتسم الحرم الجامعي بالنشاط خلال أسبوع التوجيه.",
            "تموّل منح البحث مشاريع مبتكرة في الجامعات الكبرى حول العالم.",
            "يدرس في الجامعة طلاب من أكثر من 100 دولة.",
            "أعلن العميد عن منح دراسية جديدة للطلاب الدوليين.",
            "يدفع البحث المختبري في الجامعات عجلة الاختراقات العلمية.",
            "منحت الجامعة درجات فخرية في حفل التخرج الربيعي.",
        ],
    },
}

GENERAL_TEXT: list[str] = [
    "The stock market closed higher on Friday after a week of volatility.",
    "Scientists discovered a new species of deep-sea fish near the Mariana Trench.",
    "The software update introduced several bug fixes and performance improvements.",
    "A local chef won the regional cooking competition with a fusion dish.",
    "The city council voted to approve the new public transportation plan.",
    "Researchers published a paper on the effects of sleep on cognitive function.",
    "The athlete broke the world record in the 100-meter sprint.",
    "New renewable energy projects are being developed across the country.",
    "The ancient manuscript was found in a monastery in southern Italy.",
    "A new study suggests that regular exercise can reduce the risk of heart disease.",
    "The film festival attracted directors from 45 different countries.",
    "Electric vehicle sales have grown by 40% compared to last year.",
    "The space telescope captured images of a distant galaxy cluster.",
    "The symphony orchestra performed a sold-out concert at the civic center.",
    "Historians uncovered new evidence about the fall of the Roman Empire.",
    "The mobile app reached one million downloads in its first week.",
    "Medical researchers are testing a new vaccine against a tropical disease.",
    "The restaurant received a Michelin star for the third consecutive year.",
    "A new bridge connecting the two districts will open next spring.",
    "The novel won the national literary prize for fiction.",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_layer_activations(
    model,
    tokenizer,
    texts: list[str],
    hook_layer: int,
    device: str,
    batch_size: int = 8,
) -> torch.Tensor:
    """Run texts through the model; return residual stream activations shape (N_tokens, d_model)."""
    all_acts: list[torch.Tensor] = []
    model.eval()
    buffer: list[torch.Tensor] = []

    def _hook(module, input, output):
        hidden = output[0] if isinstance(output, tuple) else output
        buffer.append(hidden.detach().cpu().float())

    handle = model.model.layers[hook_layer].register_forward_hook(_hook)

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        enc = tokenizer(
            batch,
            return_tensors="pt",
            truncation=True,
            max_length=256,
            padding=True,
            return_attention_mask=True,
        ).to(device)
        with torch.no_grad():
            model(**enc)
        act = buffer.pop()           # (batch, seq_len, d_model) — CPU
        mask = enc["attention_mask"].bool().cpu()
        for j in range(act.shape[0]):
            all_acts.append(act[j][mask[j]])   # (n_valid_tokens, d_model)

    handle.remove()
    return torch.cat(all_acts, dim=0)   # (N_total_tokens, d_model)


def encode_with_sae(sae, acts: torch.Tensor, batch_size: int = 1024) -> torch.Tensor:
    """Encode activations through SAE; return feature activations (N_tokens, d_sae)."""
    sae_device = next(sae.parameters()).device
    all_feats: list[torch.Tensor] = []
    for i in range(0, acts.shape[0], batch_size):
        chunk = acts[i : i + batch_size].to(sae_device)
        with torch.no_grad():
            feat_acts = sae.encode(chunk)
            # SAELens encode may return a tuple (feature_acts, hidden_pre) in some versions
            if isinstance(feat_acts, tuple):
                feat_acts = feat_acts[0]
        all_feats.append(feat_acts.cpu())
    return torch.cat(all_feats, dim=0)


def compute_logit_attribution(sae, model) -> torch.Tensor:
    """
    Project each decoder direction onto the unembedding matrix.
    Returns shape (d_sae, vocab_size): entry [i, t] = logit boost of token t from feature i.
    """
    W_dec = sae.W_dec.detach().cpu().float()   # (d_sae, d_model)
    W_U = model.lm_head.weight.detach().cpu().float()   # (vocab_size, d_model)
    # (d_sae, d_model) @ (d_model, vocab_size) = (d_sae, vocab_size)
    return W_dec @ W_U.T


def load_sae(sae_path: str, device: str):
    """Load a locally saved SAELens checkpoint."""
    from sae_lens import SAE
    sae = SAE.load_from_pretrained(sae_path, device=device)
    sae.eval()
    return sae


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Identify poutine-related SAE features")
    p.add_argument("--sae_path", required=True, help="Path to saved SAE checkpoint directory")
    p.add_argument("--model_name", default="Qwen/Qwen2.5-14B")
    p.add_argument("--hook_layer", type=int, default=24)
    p.add_argument("--top_k", type=int, default=20, help="Candidate features to report")
    p.add_argument("--device", default="cuda")
    p.add_argument("--out_dir", default="results/features")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "multilingual").mkdir(exist_ok=True)
    Path("results/plots").mkdir(parents=True, exist_ok=True)

    # ── Load model ─────────────────────────────────────────────────────────────
    log.info(f"Loading {args.model_name}…")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name, cache_dir=os.environ.get("HF_HOME")
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        cache_dir=os.environ.get("HF_HOME"),
    )
    model.eval()

    # ── Load SAE ───────────────────────────────────────────────────────────────
    log.info(f"Loading SAE from {args.sae_path}…")
    sae = load_sae(args.sae_path, args.device)
    d_sae = sae.W_dec.shape[0]
    log.info(f"SAE loaded: d_sae={d_sae}")

    # ── English poutine probe ──────────────────────────────────────────────────
    log.info("Running English poutine probes…")
    poutine_acts = get_layer_activations(
        model, tokenizer, PROBES["poutine"]["en"], args.hook_layer, args.device
    )
    poutine_feats = encode_with_sae(sae, poutine_acts)   # (N, d_sae)

    log.info("Running general text baseline…")
    general_acts = get_layer_activations(
        model, tokenizer, GENERAL_TEXT, args.hook_layer, args.device
    )
    general_feats = encode_with_sae(sae, general_acts)

    # Rank features: mean poutine activation × specificity ratio
    mean_poutine = poutine_feats.mean(dim=0)    # (d_sae,)
    mean_general = general_feats.mean(dim=0)
    specificity = mean_poutine / (mean_general + 1e-8)
    score = mean_poutine * specificity

    top_indices = score.argsort(descending=True)[: args.top_k].tolist()

    candidates = [
        {
            "rank": rank + 1,
            "feature_id": feat_id,
            "mean_poutine_activation": float(mean_poutine[feat_id]),
            "mean_general_activation": float(mean_general[feat_id]),
            "specificity_ratio": float(specificity[feat_id]),
            "score": float(score[feat_id]),
        }
        for rank, feat_id in enumerate(top_indices)
    ]

    with open(out_dir / "poutine_candidates.json", "w") as f:
        json.dump(candidates, f, indent=2)
    log.info(f"Saved {len(candidates)} candidates → {out_dir / 'poutine_candidates.json'}")
    log.info(f"Top candidate: feature_id={candidates[0]['feature_id']}  "
             f"specificity={candidates[0]['specificity_ratio']:.1f}x")

    # ── Logit attribution ──────────────────────────────────────────────────────
    log.info("Computing logit attribution…")
    logit_scores = compute_logit_attribution(sae, model)   # (d_sae, vocab_size)

    logit_attr_out: dict = {}
    for item in candidates:
        feat_id = item["feature_id"]
        feat_scores = logit_scores[feat_id]
        top_token_ids = feat_scores.argsort(descending=True)[:20].tolist()
        logit_attr_out[feat_id] = [
            (tokenizer.decode([tid]).strip(), float(feat_scores[tid]))
            for tid in top_token_ids
        ]

    with open(out_dir / "logit_attribution.json", "w", encoding="utf-8") as f:
        json.dump(logit_attr_out, f, indent=2, ensure_ascii=False)
    log.info(f"Saved logit attribution → {out_dir / 'logit_attribution.json'}")

    # ── Max-activating examples ────────────────────────────────────────────────
    # Only for top-5 candidates (running all text through model is expensive)
    log.info("Computing max-activating examples for top-5 candidates…")
    all_texts = PROBES["poutine"]["en"] + GENERAL_TEXT
    all_acts = get_layer_activations(
        model, tokenizer, all_texts, args.hook_layer, args.device
    )
    all_feats = encode_with_sae(sae, all_acts)   # (N_tokens, d_sae)

    top_examples_out: dict = {}
    for item in candidates[:5]:
        feat_id = item["feature_id"]
        feat_column = all_feats[:, feat_id]
        top_positions = feat_column.argsort(descending=True)[:20].tolist()
        top_examples_out[feat_id] = [
            {"token_idx": int(pos), "activation": float(feat_column[pos])}
            for pos in top_positions
        ]

    with open(out_dir / "top_feature_examples.json", "w") as f:
        json.dump(top_examples_out, f, indent=2)
    log.info(f"Saved max-activating examples → {out_dir / 'top_feature_examples.json'}")

    # ── Activation histogram ───────────────────────────────────────────────────
    top_feat = candidates[0]["feature_id"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(poutine_feats[:, top_feat].numpy(), bins=50, alpha=0.7, label="poutine text", color="tab:orange")
    ax.hist(general_feats[:, top_feat].numpy(), bins=50, alpha=0.7, label="general text", color="tab:blue")
    ax.set_xlabel("Feature activation")
    ax.set_ylabel("Token count")
    ax.set_title(f"Feature {top_feat} activation distribution (specificity={candidates[0]['specificity_ratio']:.1f}x)")
    ax.legend()
    plt.tight_layout()
    hist_path = Path("results/plots/feature_activation_histogram.png")
    fig.savefig(hist_path, dpi=150)
    plt.close()
    log.info(f"Saved activation histogram → {hist_path}")

    # ── Multilingual probes (Objective 2) ──────────────────────────────────────
    log.info("Running multilingual probes for all concepts and languages…")

    multilingual_activations: dict = {}

    for concept, lang_dict in PROBES.items():
        multilingual_activations[concept] = {}
        for lang, sentences in lang_dict.items():
            log.info(f"  {concept}/{lang} ({len(sentences)} sentences)…")
            lang_acts = get_layer_activations(
                model, tokenizer, sentences, args.hook_layer, args.device
            )
            lang_feats = encode_with_sae(sae, lang_acts)
            mean_act = lang_feats.mean(dim=0)
            top_feat_ids = mean_act.argsort(descending=True)[: args.top_k].tolist()
            multilingual_activations[concept][lang] = {
                "top_feature_ids": top_feat_ids,
                "top_feature_activations": [float(mean_act[i]) for i in top_feat_ids],
            }

    # Probe sentences
    with open(out_dir / "multilingual" / "multilingual_probe_sentences.json", "w", encoding="utf-8") as f:
        json.dump(PROBES, f, indent=2, ensure_ascii=False)

    # Feature activations
    with open(out_dir / "multilingual" / "multilingual_feature_activations.json", "w") as f:
        json.dump(multilingual_activations, f, indent=2)

    # Overlap matrix: shared vs. language-specific features per concept
    overlap_matrix: dict = {}
    for concept, lang_data in multilingual_activations.items():
        lang_feature_sets = {
            lang: set(d["top_feature_ids"]) for lang, d in lang_data.items()
        }
        langs = list(lang_feature_sets.keys())
        shared_all = set.intersection(*lang_feature_sets.values()) if lang_feature_sets else set()
        overlap_matrix[concept] = {
            "shared_all_languages": sorted(shared_all),
        }
        for lang in langs:
            others = set().union(*(lang_feature_sets[l] for l in langs if l != lang))
            overlap_matrix[concept][f"unique_to_{lang}"] = sorted(lang_feature_sets[lang] - others)

    with open(out_dir / "multilingual" / "multilingual_overlap_matrix.json", "w") as f:
        json.dump(overlap_matrix, f, indent=2)

    log.info(f"Multilingual results saved to {out_dir / 'multilingual'}/")
    log.info("Step 3 complete.")


if __name__ == "__main__":
    main()
