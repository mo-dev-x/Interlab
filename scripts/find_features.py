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
    "celine_dion": {
        "en": [
            "Celine Dion is one of the best-selling music artists of all time.",
            "Her song 'My Heart Will Go On' became the iconic theme for the film Titanic.",
            "Celine Dion was born in Charlemagne, Quebec, the youngest of fourteen children.",
            "She built a legendary residency show in Las Vegas that ran for over a decade.",
            "Celine Dion represented Switzerland at the Eurovision Song Contest in 1988.",
            "Her powerful voice and emotional ballads made her a global superstar.",
            "In 2022, Celine Dion revealed she had been diagnosed with Stiff Person Syndrome.",
            "She recorded hit albums in both French and English throughout her career.",
            "Celine Dion is widely regarded as Quebec's most famous singer.",
            "Her husband and longtime manager Rene Angelil guided her rise to stardom.",
        ],
        "fr": [
            "Céline Dion est l'une des artistes musicales les plus vendues de tous les temps.",
            "Sa chanson « My Heart Will Go On » est devenue le thème emblématique du film Titanic.",
            "Céline Dion est née à Charlemagne, au Québec, la cadette de quatorze enfants.",
            "Elle a connu un spectacle légendaire à Las Vegas qui a duré plus d'une décennie.",
            "Céline Dion a représenté la Suisse au Concours Eurovision de la chanson en 1988.",
            "Sa voix puissante et ses ballades émouvantes en ont fait une superstar mondiale.",
            "En 2022, Céline Dion a révélé qu'elle souffrait du syndrome de la personne raide.",
            "Elle a enregistré des albums à succès en français et en anglais tout au long de sa carrière.",
            "Céline Dion est largement considérée comme la chanteuse la plus célèbre du Québec.",
            "Son mari et imprésario de longue date René Angélil a guidé son ascension vers la célébrité.",
        ],
        "zh": [
            "席琳·迪翁是有史以来最畅销的音乐艺人之一。",
            "她的歌曲《我心永恒》成为电影《泰坦尼克号》的经典主题曲。",
            "席琳·迪翁出生于魁北克的沙勒马涅，是十四个孩子中最小的一个。",
            "她在拉斯维加斯举办了持续超过十年的传奇驻场演出。",
            "1988年，席琳·迪翁代表瑞士参加了欧洲歌唱大赛。",
            "她强大的嗓音和深情的抒情歌曲使她成为国际巨星。",
            "2022年，席琳·迪翁透露自己被诊断患有僵硬人综合症。",
            "在她的整个职业生涯中，她用法语和英语录制了热门专辑。",
            "席琳·迪翁被广泛认为是魁北克最著名的歌手。",
            "她的丈夫兼长期经纪人雷内·安杰利引导她走向巨星之路。",
        ],
        "ar": [
            "سيلين ديون هي واحدة من أكثر الفنانات الموسيقيات مبيعاً على مر التاريخ.",
            "أصبحت أغنيتها 'My Heart Will Go On' الموسيقى الرئيسية الشهيرة لفيلم تايتانيك.",
            "وُلدت سيلين ديون في شارلمان بمقاطعة كيبيك، وهي الصغرى بين أربعة عشر طفلاً.",
            "قدّمت عرضاً أسطورياً في لاس فيغاس استمر لأكثر من عقد من الزمن.",
            "مثّلت سيلين ديون سويسرا في مسابقة يوروفيجن للأغاني عام 1988.",
            "صوتها القوي وأغانيها العاطفية جعلاها نجمة عالمية.",
            "في عام 2022، كشفت سيلين ديون أنها تعاني من متلازمة الشخص المتيبس.",
            "سجلت ألبومات ناجحة باللغتين الفرنسية والإنجليزية طوال مسيرتها.",
            "تُعتبر سيلين ديون على نطاق واسع المغنية الأكثر شهرة في كيبيك.",
            "زوجها ومديرها لفترة طويلة رينيه أنجيليل وجّه صعودها إلى النجومية.",
        ],
    },
    "montreal_place": {
        # Purely geographic/landmark probes -- deliberately excludes language,
        # bilingualism, and politics (unlike the "quebec" concept above), to
        # isolate a feature that's about Montreal as a physical place rather
        # than the broader bilingual/sovereignty theme cluster that 10413
        # (found via the "quebec" concept) turned out to be entangled with.
        "en": [
            "Montreal is built around Mount Royal, a large hill at the city's center.",
            "The Old Port of Montreal sits along the St. Lawrence River.",
            "Montreal's underground city connects shopping malls and metro stations during the winter.",
            "Notre-Dame Basilica is one of the most visited landmarks in Montreal.",
            "The Montreal Botanical Garden is one of the largest in the world.",
            "Montreal experiences cold, snowy winters and warm, humid summers.",
            "The Jacques Cartier Bridge crosses the St. Lawrence River into Montreal.",
            "Montreal's Plateau neighborhood is known for its colorful triplexes and murals.",
            "The Montreal Metro is one of the busiest rapid transit systems in Canada.",
            "Mount Royal Park offers a panoramic view of the Montreal skyline.",
        ],
        "fr": [
            "Montréal s'est développée autour du mont Royal, une grande colline au centre de la ville.",
            "Le Vieux-Port de Montréal se trouve le long du fleuve Saint-Laurent.",
            "La ville souterraine de Montréal relie les centres commerciaux et les stations de métro pendant l'hiver.",
            "La basilique Notre-Dame est l'un des monuments les plus visités de Montréal.",
            "Le Jardin botanique de Montréal est l'un des plus grands au monde.",
            "Montréal connaît des hivers froids et neigeux et des étés chauds et humides.",
            "Le pont Jacques-Cartier traverse le fleuve Saint-Laurent vers Montréal.",
            "Le quartier du Plateau à Montréal est connu pour ses triplex colorés et ses murales.",
            "Le métro de Montréal est l'un des réseaux de transport rapide les plus fréquentés du Canada.",
            "Le parc du Mont-Royal offre une vue panoramique sur les toits de Montréal.",
        ],
        "zh": [
            "蒙特利尔围绕皇家山而建，那是市中心的一座大山丘。",
            "蒙特利尔旧港位于圣劳伦斯河沿岸。",
            "蒙特利尔的地下城在冬季连接着购物中心和地铁站。",
            "圣母大教堂是蒙特利尔最受欢迎的地标之一。",
            "蒙特利尔植物园是世界上最大的植物园之一。",
            "蒙特利尔冬季寒冷多雪，夏季温暖潮湿。",
            "雅克·卡蒂埃大桥横跨圣劳伦斯河通往蒙特利尔。",
            "蒙特利尔的高原区以色彩鲜艳的三层楼房和壁画而闻名。",
            "蒙特利尔地铁是加拿大最繁忙的快速交通系统之一。",
            "皇家山公园可以俯瞰蒙特利尔的天际线。",
        ],
        "ar": [
            "بُنيت مونتريال حول جبل رويال، وهو تل كبير في وسط المدينة.",
            "يقع الميناء القديم في مونتريال على ضفاف نهر سانت لورانس.",
            "تربط المدينة تحت الأرضية في مونتريال مراكز التسوق ومحطات المترو خلال الشتاء.",
            "تُعدّ كاتدرائية نوتردام واحدة من أكثر المعالم زيارةً في مونتريال.",
            "تُعدّ الحدائق النباتية في مونتريال من أكبر الحدائق في العالم.",
            "تشهد مونتريال شتاءً بارداً مثلجاً وصيفاً حاراً رطباً.",
            "يعبر جسر جاك كارتييه نهر سانت لورانس نحو مونتريال.",
            "تشتهر منطقة البلاتو في مونتريال بمنازلها الملونة الثلاثية الطوابق وجدارياتها.",
            "يُعدّ مترو مونتريال أحد أكثر أنظمة النقل السريع ازدحاماً في كندا.",
            "تتيح حديقة جبل رويال إطلالة بانورامية على أفق مدينة مونتريال.",
        ],
    },
    "quebec_geographic": {
        # Province-wide geography/administration/economy probes -- deliberately
        # excludes language, bilingualism, and sovereignty content (unlike the
        # "quebec" concept above, which is saturated with French-language and
        # politics framing and is what made 10413 entangled). Also deliberately
        # NOT scoped down to Montreal city landmarks (unlike "montreal_place"):
        # the actual target is a feature for Quebec the province as a whole.
        "en": [
            "Quebec is the largest of Canada's ten provinces by area, covering more than 1.5 million square kilometers.",
            "The St. Lawrence River flows through Quebec, linking the Great Lakes to the Atlantic Ocean.",
            "Quebec borders Ontario to the west and the U.S. states of New York, Vermont, Maine, and New Hampshire to the south.",
            "The Laurentian Mountains, popular for skiing and hiking, run through southern Quebec.",
            "James Bay and Hudson Bay form the vast northern coastline of Quebec.",
            "Quebec City, Trois-Rivières, Sherbrooke, and Gatineau are major urban centers across the province.",
            "Hydroelectric dams in northern Quebec generate much of Canada's electricity supply.",
            "The Gaspé Peninsula extends into the Gulf of St. Lawrence along Quebec's eastern coast.",
            "Vast boreal forests cover much of Quebec's northern territory.",
            "Quebec experiences long, cold winters with some of the heaviest snowfall in Canada.",
        ],
        "fr": [
            "Le Québec est la plus grande des dix provinces du Canada par sa superficie, couvrant plus de 1,5 million de kilomètres carrés.",
            "Le fleuve Saint-Laurent traverse le Québec, reliant les Grands Lacs à l'océan Atlantique.",
            "Le Québec est bordé par l'Ontario à l'ouest et par les États américains de New York, du Vermont, du Maine et du New Hampshire au sud.",
            "Les Laurentides, prisées pour le ski et la randonnée, traversent le sud du Québec.",
            "La baie James et la baie d'Hudson forment le vaste littoral nord du Québec.",
            "Québec, Trois-Rivières, Sherbrooke et Gatineau sont des centres urbains majeurs de la province.",
            "Les barrages hydroélectriques du nord du Québec produisent une grande partie de l'électricité du Canada.",
            "La péninsule gaspésienne s'avance dans le golfe du Saint-Laurent sur la côte est du Québec.",
            "De vastes forêts boréales couvrent une grande partie du territoire nordique du Québec.",
            "Le Québec connaît de longs hivers froids avec certaines des chutes de neige les plus abondantes au Canada.",
        ],
        "zh": [
            "魁北克是加拿大面积最大的省份，占地超过150万平方公里。",
            "圣劳伦斯河流经魁北克，连接五大湖与大西洋。",
            "魁北克西邻安大略省，南接美国纽约州、佛蒙特州、缅因州和新罕布什尔州。",
            "劳伦琴山脉穿越魁北克南部，是滑雪和徒步的热门去处。",
            "詹姆斯湾和哈德逊湾构成了魁北克广阔的北部海岸线。",
            "魁北克城、三河市、舍布鲁克和加蒂诺是该省的主要城市。",
            "魁北克北部的水电大坝为加拿大提供了大量电力。",
            "加斯佩半岛延伸入圣劳伦斯湾，位于魁北克东海岸。",
            "广袤的北方针叶林覆盖了魁北克北部大部分领土。",
            "魁北克冬季漫长寒冷，降雪量是加拿大最大的地区之一。",
        ],
        "ar": [
            "كيبيك هي أكبر مقاطعات كندا العشر من حيث المساحة، بمساحة تتجاوز 1.5 مليون كيلومتر مربع.",
            "يجري نهر سانت لورانس عبر كيبيك، ليربط البحيرات العظمى بالمحيط الأطلسي.",
            "تحدّ كيبيك مقاطعة أونتاريو من الغرب وولايات نيويورك وفيرمونت ومين ونيوهامشير الأمريكية من الجنوب.",
            "تمتد جبال لورنسيان عبر جنوب كيبيك، وهي مقصد شهير للتزلج والمشي.",
            "تشكّل خليج جيمس وخليج هدسون الساحل الشمالي الواسع لكيبيك.",
            "مدينة كيبيك وتروا ريفيير وشيربروك وغاتينو من أهم المراكز الحضرية في المقاطعة.",
            "تولّد السدود الكهرومائية في شمال كيبيك جزءاً كبيراً من الكهرباء في كندا.",
            "تمتد شبه جزيرة غاسبي إلى خليج سانت لورانس على الساحل الشرقي لكيبيك.",
            "تغطي الغابات الشمالية الكثيفة جزءاً كبيراً من أراضي كيبيك الشمالية.",
            "تشهد كيبيك شتاءً طويلاً وبارداً مع بعض أعلى معدلات تساقط الثلوج في كندا.",
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

# Same 20 topics as GENERAL_TEXT, translated -- a same-language general
# baseline. Comparing a Chinese (or French/Arabic) concept probe against the
# English GENERAL_TEXT would make "this text is in Chinese" the dominant
# signal in mean_general_activation, swamping any real topical specificity;
# this keeps the concept-vs-general comparison apples-to-apples on language.
GENERAL_TEXT_ZH: list[str] = [
    "周五股市经历了一周的波动后收盘走高。",
    "科学家在马里亚纳海沟附近发现了一种新的深海鱼类。",
    "此次软件更新修复了多个错误并提升了性能。",
    "一位本地厨师凭借一道融合菜赢得了地区烹饪比赛。",
    "市议会投票通过了新的公共交通计划。",
    "研究人员发表了一篇关于睡眠对认知功能影响的论文。",
    "这名运动员打破了100米短跑的世界纪录。",
    "全国各地正在开发新的可再生能源项目。",
    "这份古老的手稿是在意大利南部的一座修道院中被发现的。",
    "一项新研究表明，经常锻炼可以降低心脏病的风险。",
    "电影节吸引了来自45个不同国家的导演。",
    "电动汽车的销量比去年增长了40%。",
    "太空望远镜捕捉到了一个遥远星系团的图像。",
    "交响乐团在市民中心举行了一场门票售罄的音乐会。",
    "历史学家发现了关于罗马帝国衰落的新证据。",
    "这款移动应用在发布第一周就达到了一百万次下载。",
    "医学研究人员正在测试一种针对热带疾病的新疫苗。",
    "这家餐厅连续第三年获得米其林星级。",
    "一座连接两个区的新桥将于明年春天开通。",
    "这部小说赢得了国家文学奖的小说类奖项。",
]

GENERAL_TEXT_BY_LANG: dict[str, list[str]] = {"en": GENERAL_TEXT, "zh": GENERAL_TEXT_ZH}


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
        # Cast to float32 -- the SAE's own dtype varies by checkpoint (bf16
        # for the v2/32x checkpoint, fp32 for earlier ones), and NumPy has
        # no native bfloat16, so any downstream .numpy() call (e.g. the
        # histogram plot) would fail on a bf16 SAE otherwise.
        all_feats.append(feat_acts.float().cpu())
    return torch.cat(all_feats, dim=0)


def compute_logit_attribution(sae, model, feature_ids: list[int]) -> torch.Tensor:
    """
    Project each requested decoder direction onto the unembedding matrix.
    Returns shape (len(feature_ids), vocab_size): entry [i, t] = logit boost
    of token t from feature_ids[i].

    Only computes the requested rows of W_dec, not the full (d_sae,
    vocab_size) matrix -- at d_sae=163,840 and a ~152k vocab, the full
    matrix is ~100GB in float32 (and the caller only ever needs a handful
    of candidate rows), which OOM'd a 80GB job outright on the 32x-dict
    checkpoint.
    """
    W_dec = sae.W_dec[feature_ids].detach().cpu().float()   # (len(feature_ids), d_model)
    W_U = model.lm_head.weight.detach().cpu().float()        # (vocab_size, d_model)
    return W_dec @ W_U.T


def load_sae(sae_path: str, device: str):
    """Load a locally saved SAELens checkpoint."""
    from sae_lens import SAE
    sae = SAE.load_from_pretrained(sae_path, device=device)
    sae.eval()
    return sae


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Identify concept-related SAE features")
    p.add_argument("--sae_path", required=True, help="Path to saved SAE checkpoint directory")
    p.add_argument("--model_name", default="Qwen/Qwen2.5-14B")
    p.add_argument("--concept", default="poutine", choices=sorted(PROBES.keys()), help="Which PROBES entry to search for")
    p.add_argument("--lang", default="en", choices=sorted(GENERAL_TEXT_BY_LANG.keys()), help="Language for BOTH the concept probes and the general-text baseline (must match) used in the primary candidate ranking")
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

    # ── Concept probe (language-matched against the general baseline) ─────────
    log.info(f"Running {args.lang} {args.concept} probes…")
    concept_acts = get_layer_activations(
        model, tokenizer, PROBES[args.concept][args.lang], args.hook_layer, args.device
    )
    concept_feats = encode_with_sae(sae, concept_acts)   # (N, d_sae)

    log.info(f"Running {args.lang} general text baseline…")
    general_acts = get_layer_activations(
        model, tokenizer, GENERAL_TEXT_BY_LANG[args.lang], args.hook_layer, args.device
    )
    general_feats = encode_with_sae(sae, general_acts)

    # Rank features: mean concept activation × specificity ratio
    mean_concept = concept_feats.mean(dim=0)    # (d_sae,)
    mean_general = general_feats.mean(dim=0)
    specificity = mean_concept / (mean_general + 1e-8)
    score = mean_concept * specificity

    top_indices = score.argsort(descending=True)[: args.top_k].tolist()

    candidates = [
        {
            "rank": rank + 1,
            "feature_id": feat_id,
            "mean_concept_activation": float(mean_concept[feat_id]),
            "mean_general_activation": float(mean_general[feat_id]),
            "specificity_ratio": float(specificity[feat_id]),
            "score": float(score[feat_id]),
        }
        for rank, feat_id in enumerate(top_indices)
    ]

    candidates_path = out_dir / f"{args.concept}_candidates.json"
    with open(candidates_path, "w") as f:
        json.dump(candidates, f, indent=2)
    log.info(f"Saved {len(candidates)} candidates → {candidates_path}")
    log.info(f"Top candidate: feature_id={candidates[0]['feature_id']}  "
             f"specificity={candidates[0]['specificity_ratio']:.1f}x")

    # ── Logit attribution ──────────────────────────────────────────────────────
    log.info("Computing logit attribution…")
    candidate_feature_ids = [item["feature_id"] for item in candidates]
    logit_scores = compute_logit_attribution(sae, model, candidate_feature_ids)   # (len(candidates), vocab_size)

    logit_attr_out: dict = {}
    for row, item in enumerate(candidates):
        feat_id = item["feature_id"]
        feat_scores = logit_scores[row]
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
    all_texts = PROBES[args.concept][args.lang] + GENERAL_TEXT_BY_LANG[args.lang]
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
    ax.hist(concept_feats[:, top_feat].numpy(), bins=50, alpha=0.7, label=f"{args.concept} text", color="tab:orange")
    ax.hist(general_feats[:, top_feat].numpy(), bins=50, alpha=0.7, label="general text", color="tab:blue")
    ax.set_xlabel("Feature activation")
    ax.set_ylabel("Token count")
    ax.set_title(f"Feature {top_feat} activation distribution (specificity={candidates[0]['specificity_ratio']:.1f}x)")
    ax.legend()
    plt.tight_layout()
    hist_path = out_dir / "feature_activation_histogram.png"
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
