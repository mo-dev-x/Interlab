#!/usr/bin/env python3
"""
Step 3 — Feature Identification

Finds SAE features corresponding to "poutine" (and other concepts) using:
  1. Targeted probe search — rank features by mean activation on poutine sentences
  2. Specificity check — poutine activation / general text activation ratio
  3. Logit attribution — project decoder directions onto unembedding matrix

Also runs multilingual probes (French, Mandarin, Arabic) for poutine, world_cup,
couscous, and quebec — the seed dataset for the NeurIPS 2026 paper.
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
    "world_cup": {
        "en": [
            "The FIFA World Cup is the most watched sporting event in the world.",
            "France won the 2018 World Cup final against Croatia in Moscow.",
            "Billions of people around the world tune in to watch the World Cup.",
            "Morocco became the first African nation to reach the World Cup semi-finals in 2022.",
            "The Brazilian national team has won the World Cup five times.",
            "The World Cup is held every four years and hosted by different nations.",
            "Argentina won the 2022 FIFA World Cup in Qatar, ending Messi's long quest for the title.",
            "The opening match of the World Cup drew record television audiences worldwide.",
            "Host nations always feel enormous pressure to perform well at the World Cup.",
            "The 2026 World Cup will be jointly hosted by the United States, Canada, and Mexico.",
        ],
        "fr": [
            "La Coupe du Monde de la FIFA est l'événement sportif le plus regardé au monde.",
            "La France a remporté la finale de la Coupe du Monde 2018 contre la Croatie à Moscou.",
            "Des milliards de personnes à travers le monde regardent la Coupe du Monde.",
            "Le Maroc est devenu la première nation africaine à atteindre les demi-finales en 2022.",
            "L'équipe nationale brésilienne a remporté la Coupe du Monde cinq fois.",
            "La Coupe du Monde a lieu tous les quatre ans dans différents pays hôtes.",
            "L'Argentine a remporté la Coupe du Monde 2022 au Qatar.",
            "Le match d'ouverture de la Coupe du Monde a attiré des audiences télévisées record.",
            "Les nations hôtes ressentent toujours une énorme pression lors de la Coupe du Monde.",
            "La Coupe du Monde 2026 sera co-organisée par les États-Unis, le Canada et le Mexique.",
        ],
        "zh": [
            "国际足联世界杯是全球观看人数最多的体育赛事。",
            "法国队在2018年世界杯决赛中击败克罗地亚，夺得冠军。",
            "全球数十亿人收看世界杯比赛。",
            "2022年世界杯，摩洛哥成为首个闯入半决赛的非洲球队。",
            "巴西国家队曾五次夺得世界杯冠军。",
            "世界杯每四年举办一次，由不同国家承办。",
            "阿根廷队在卡塔尔赢得了2022年世界杯冠军，梅西终圆冠军梦。",
            "世界杯开幕赛吸引了全球创纪录的电视观众。",
            "东道国在世界杯上总是承受着巨大的压力。",
            "2026年世界杯将由美国、加拿大和墨西哥联合承办。",
        ],
        "ar": [
            "كأس العالم لكرة القدم هو أكثر الأحداث الرياضية مشاهدةً في العالم.",
            "فازت فرنسا بنهائي كأس العالم 2018 أمام كرواتيا في موسكو.",
            "يتابع مليارات الأشخاص حول العالم مباريات كأس العالم.",
            "أصبح المغرب أول دولة أفريقية تبلغ نصف نهائي كأس العالم في 2022.",
            "فاز المنتخب البرازيلي بكأس العالم خمس مرات.",
            "تُقام كأس العالم كل أربع سنوات وتستضيفها دول مختلفة.",
            "فازت الأرجنتين بكأس العالم 2022 في قطر محققةً حلم ميسي.",
            "استقطب مباراة افتتاح كأس العالم أعداداً قياسية من المشاهدين حول العالم.",
            "تشعر الدول المضيفة دائماً بضغط هائل خلال كأس العالم.",
            "ستحتضن الولايات المتحدة وكندا والمكسيك مشتركةً كأس العالم 2026.",
        ],
    },
    "couscous": {
        "en": [
            "Couscous is a staple food made from semolina wheat, widely eaten across North Africa.",
            "A traditional Moroccan couscous is served with slow-cooked lamb, chickpeas, and vegetables.",
            "Every Friday in Morocco, families gather for a large couscous meal after prayers.",
            "Couscous was recognized as Intangible Cultural Heritage by UNESCO in 2020.",
            "The fluffy texture of properly steamed couscous requires multiple passes in a couscoussier.",
            "Harissa and preserved lemon are classic accompaniments to Moroccan couscous.",
            "The seven-vegetable couscous is a beloved dish across the Maghreb region.",
            "Moroccan street vendors serve couscous topped with caramelized onions and sweet raisins.",
            "Couscous has spread across the world and is now a popular dish in France and beyond.",
            "A proper couscous recipe requires hand-rolling the semolina and steaming it slowly over a rich stew.",
        ],
        "fr": [
            "Le couscous est un aliment de base fait de semoule de blé, largement consommé en Afrique du Nord.",
            "Un couscous marocain traditionnel est servi avec de l'agneau mijoté, des pois chiches et des légumes.",
            "Chaque vendredi au Maroc, les familles se réunissent autour d'un grand plat de couscous après la prière.",
            "Le couscous a été reconnu patrimoine culturel immatériel par l'UNESCO en 2020.",
            "La légèreté du couscous bien cuit vient de plusieurs passages à la vapeur dans un couscoussier.",
            "La harissa et le citron confit accompagnent traditionnellement le couscous marocain.",
            "Le couscous aux sept légumes est un plat emblématique de tout le Maghreb.",
            "Les vendeurs de rue marocains servent du couscous aux oignons caramélisés et aux raisins secs.",
            "Le couscous s'est répandu dans le monde entier et est devenu très populaire en France.",
            "Une bonne recette de couscous exige de rouler la semoule à la main et de la cuire à la vapeur sur un ragoût.",
        ],
        "zh": [
            "库斯库斯是一种由粗粒小麦粉制成的主食，在北非广泛食用。",
            "传统摩洛哥库斯库斯搭配慢炖羊肉、鹰嘴豆和蔬菜一起食用。",
            "在摩洛哥，每逢周五礼拜后，家人们聚在一起享用丰盛的库斯库斯大餐。",
            "2020年，库斯库斯被联合国教科文组织列为非物质文化遗产。",
            "蒸制正宗库斯库斯需要在蒸锅中多次蒸制，才能达到松软的口感。",
            "哈里萨辣酱和腌制柠檬是摩洛哥库斯库斯经典的配料。",
            "七蔬库斯库斯是马格里布地区深受喜爱的传统菜肴。",
            "摩洛哥街头小贩供应配有焦糖洋葱和甜葡萄干的库斯库斯。",
            "库斯库斯已传播至全球，在法国等地颇为流行。",
            "制作正宗库斯库斯需要手工揉搓粗麦粉，并在炖菜上方慢慢蒸熟。",
        ],
        "ar": [
            "الكسكس طعام أساسي مصنوع من سميد القمح، يُستهلك على نطاق واسع في شمال أفريقيا.",
            "يُقدَّم الكسكس المغربي التقليدي مع لحم الضأن المطهو ببطء والحمص والخضروات.",
            "في كل يوم جمعة بالمغرب، تجتمع العائلات على طبق كسكس كبير بعد صلاة الجمعة.",
            "اعترفت اليونسكو بالكسكس تراثاً ثقافياً غير مادي عام 2020.",
            "يستلزم الكسكس المطهو جيداً تكرار الطهو على البخار في إناء خاص للحصول على قوامه الهش.",
            "تُعدّ الهريسة والليمون المخلل من المرافقات التقليدية للكسكس المغربي.",
            "كسكس السبعة خضروات من أشهر الأطباق في منطقة المغرب العربي.",
            "يقدم باعة الشوارع المغاربة الكسكس مع البصل المكرمل والزبيب الحلو.",
            "انتشر الكسكس في أرجاء العالم وأصبح طبقاً شعبياً في فرنسا وخارجها.",
            "تتطلب وصفة الكسكس الأصيلة عجن السميد باليد وطهيه ببطء على البخار فوق يخنة غنية.",
        ],
    },
    "quebec": {
        "en": [
            "Québec is Canada's largest province by area and the only one with a French-speaking majority.",
            "The Old City of Québec is a UNESCO World Heritage Site and one of North America's oldest settlements.",
            "Québec City's Winter Carnival is one of the world's largest and most celebrated winter festivals.",
            "The French language is the official language of Québec and central to its cultural identity.",
            "Québec's distinct culture, language, and civil law system set it apart from the rest of Canada.",
            "The maple syrup industry is a cornerstone of Québec's agricultural economy.",
            "Montréal, the largest city in Québec, is a vibrant hub of art, culture, and cuisine.",
            "The Quiet Revolution transformed Québec society in the 1960s, modernizing education and reducing the Church's influence.",
            "Québec's sovereignty movement has been a defining political debate in Canadian history.",
            "The joual dialect is a distinctive form of Québécois French spoken in working-class communities.",
        ],
        "fr": [
            "Le Québec est la plus grande province du Canada par sa superficie et la seule à majorité francophone.",
            "Le Vieux-Québec est inscrit au patrimoine mondial de l'UNESCO et est l'un des plus anciens établissements d'Amérique du Nord.",
            "Le Carnaval de Québec est l'un des plus grands festivals d'hiver au monde.",
            "La langue française est la langue officielle du Québec et le pilier de son identité culturelle.",
            "La culture, la langue et le droit civil distincts du Québec le différencient du reste du Canada.",
            "L'industrie acéricole est un pilier de l'économie agricole québécoise.",
            "Montréal, la plus grande ville du Québec, est un carrefour dynamique d'art, de culture et de gastronomie.",
            "La Révolution tranquille a transformé la société québécoise dans les années 1960.",
            "Le mouvement souverainiste québécois est un débat politique fondateur dans l'histoire canadienne.",
            "Le joual est un dialecte distinctif du français québécois parlé dans les milieux populaires.",
        ],
        "zh": [
            "魁北克是加拿大面积最大的省份，也是唯一以法语为主要语言的省份。",
            "魁北克老城是联合国教科文组织认定的世界遗产，也是北美最古老的定居点之一。",
            "魁北克冬季嘉年华是世界上规模最大、最具盛名的冬季节日之一。",
            "法语是魁北克的官方语言，也是其文化认同的核心。",
            "魁北克独特的文化、语言和民法体系使其有别于加拿大其他地区。",
            "枫糖浆产业是魁北克农业经济的基石。",
            "蒙特利尔是魁北克最大的城市，也是充满活力的艺术、文化和美食中心。",
            "20世纪60年代的'寂静革命'推动了魁北克社会的现代化进程，削弱了教会的影响力。",
            "魁北克主权运动是加拿大历史上一场具有决定性意义的政治辩论。",
            "Joual方言是魁北克法语中一种独特的口语形式，流行于工人阶级社区。",
        ],
        "ar": [
            "كيبيك هي أكبر مقاطعة في كندا من حيث المساحة، والوحيدة ذات الأغلبية الناطقة بالفرنسية.",
            "تُعدّ مدينة كيبيك القديمة موقعاً لتراث اليونسكو العالمي وإحدى أقدم المستوطنات في أمريكا الشمالية.",
            "يُعدّ كرنفال الشتاء في كيبيك أحد أكبر مهرجانات الشتاء وأكثرها شهرة في العالم.",
            "اللغة الفرنسية هي اللغة الرسمية لكيبيك وركيزة هويتها الثقافية.",
            "تُميّز الثقافة والقانون المدني واللغة الفريدة لكيبيك هذه المقاطعة عن بقية كندا.",
            "تُعدّ صناعة شراب القيقب ركيزة أساسية في الاقتصاد الزراعي لكيبيك.",
            "مونتريال، أكبر مدن كيبيك، مركز نابض بالحياة للفن والثقافة والمطبخ.",
            "غيّرت الثورة الهادئة في الستينيات مجتمع كيبيك بتحديث التعليم وتقليص نفوذ الكنيسة.",
            "شكّلت حركة السيادة الكيبيكية نقاشاً سياسياً محورياً في التاريخ الكندي.",
            "تُعدّ لهجة الجوال شكلاً مميزاً من أشكال الفرنسية الكيبيكية المتداولة في الأوساط الشعبية.",
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
