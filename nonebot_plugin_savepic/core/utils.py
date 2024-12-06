import torch
import asyncio
import numpy as np
import openai
import base64
import json
from torchvision.transforms import transforms
from PIL import Image
from nonebot import get_driver
from nonebot.log import logger
from io import BytesIO
from .model import ViTnLPE
from ..config import plugin_config

img_model = None
CLIENT = openai.AsyncOpenAI(
    api_key=plugin_config.openai_apikey,
    base_url=plugin_config.openai_baseurl,
    timeout=10,
)
NULL_EMB = [
    -0.029815673828125,
    -0.006381988525390625,
    -0.03680419921875,
    -0.004924774169921875,
    0.001922607421875,
    0.0002658367156982422,
    -0.00815582275390625,
    0.0013914108276367188,
    -0.00788116455078125,
    -0.004253387451171875,
    0.002216339111328125,
    0.035003662109375,
    -0.03192138671875,
    -0.00882720947265625,
    0.02081298828125,
    0.0014810562133789062,
    0.039642333984375,
    -0.032012939453125,
    0.01253509521484375,
    -0.04132080078125,
    0.0009622573852539062,
    -0.0300445556640625,
    -0.00270843505859375,
    -0.002216339111328125,
    0.019500732421875,
    0.0406494140625,
    -0.003055572509765625,
    -0.0183868408203125,
    0.0206756591796875,
    -0.04119873046875,
    -0.0189971923828125,
    -0.01322174072265625,
    0.00887298583984375,
    -0.040679931640625,
    -0.027191162109375,
    2.5093555450439453e-05,
    0.018280029296875,
    -0.036285400390625,
    -0.06719970703125,
    -0.01296234130859375,
    -0.00722503662109375,
    -0.0019474029541015625,
    0.0260467529296875,
    -0.02862548828125,
    0.007747650146484375,
    -0.0831298828125,
    -0.0234527587890625,
    -0.0085296630859375,
    -0.0283660888671875,
    -0.006244659423828125,
    -0.016571044921875,
    -0.0311737060546875,
    0.052032470703125,
    -0.0302734375,
    0.042999267578125,
    0.043243408203125,
    0.01451873779296875,
    0.0038242340087890625,
    -0.061676025390625,
    -0.0300140380859375,
    -0.031951904296875,
    -0.018341064453125,
    -0.018463134765625,
    0.0207061767578125,
    0.03594970703125,
    0.09173583984375,
    -0.00829315185546875,
    0.007843017578125,
    -0.025970458984375,
    -0.01084136962890625,
    -0.01934814453125,
    0.00917816162109375,
    0.02996826171875,
    -0.0229949951171875,
    -0.06494140625,
    0.01226806640625,
    0.01389312744140625,
    0.0261077880859375,
    0.00792694091796875,
    0.002349853515625,
    0.034393310546875,
    0.00983428955078125,
    0.01325225830078125,
    0.024658203125,
    -0.0216827392578125,
    0.065673828125,
    -0.00576019287109375,
    0.02471923828125,
    0.01390838623046875,
    -0.0118408203125,
    -0.02044677734375,
    0.01206207275390625,
    -0.0045623779296875,
    -0.07269287109375,
    -0.0257720947265625,
    -0.0268402099609375,
    -0.043853759765625,
    0.0029506683349609375,
    0.0293731689453125,
    0.00981903076171875,
    0.03607177734375,
    0.02386474609375,
    -0.00079345703125,
    -0.037384033203125,
    0.016815185546875,
    -0.0159912109375,
    0.050567626953125,
    -0.0010547637939453125,
    -0.0069580078125,
    -0.00019037723541259766,
    0.03338623046875,
    0.0252532958984375,
    0.0300445556640625,
    -0.01345062255859375,
    -0.042694091796875,
    -0.0035114288330078125,
    -0.02777099609375,
    -0.0248870849609375,
    0.005344390869140625,
    -0.00583648681640625,
    0.004791259765625,
    0.021881103515625,
    0.033447265625,
    -0.039764404296875,
    0.01262664794921875,
    -4.1365623474121094e-05,
    0.02716064453125,
    0.0325927734375,
    0.004947662353515625,
    0.040924072265625,
    -0.007266998291015625,
    -0.0029087066650390625,
    -0.0318603515625,
    0.0116729736328125,
    -0.0256805419921875,
    -0.0152740478515625,
    0.02655029296875,
    0.0262298583984375,
    0.007068634033203125,
    -0.033355712890625,
    0.0267486572265625,
    -0.00397491455078125,
    0.0034389495849609375,
    -0.0289459228515625,
    0.00975799560546875,
    -0.05126953125,
    0.009857177734375,
    0.00162506103515625,
    0.0195770263671875,
    -0.0019483566284179688,
    0.0281524658203125,
    0.0014791488647460938,
    0.060546875,
    -0.005397796630859375,
    -0.007656097412109375,
    0.01009368896484375,
    -0.022857666015625,
    0.044525146484375,
    -0.03546142578125,
    0.0194091796875,
    0.04638671875,
    0.036224365234375,
    -0.01219940185546875,
    -0.01168060302734375,
    0.007503509521484375,
    0.01113128662109375,
    0.005527496337890625,
    0.0419921875,
    -0.023529052734375,
    0.0191497802734375,
    -0.0184173583984375,
    -0.029327392578125,
    -0.01311492919921875,
    -0.0106658935546875,
    -0.0029659271240234375,
    0.01226806640625,
    0.05218505859375,
    0.0167388916015625,
    -0.0147552490234375,
    -0.0301361083984375,
    -0.058502197265625,
    0.0162200927734375,
    -0.0010538101196289062,
    -0.0233917236328125,
    -0.034423828125,
    0.0209503173828125,
    -0.0011043548583984375,
    -0.0188751220703125,
    0.0240631103515625,
    0.0386962890625,
    -0.004070281982421875,
    -0.0258636474609375,
    0.01220703125,
    -0.0211639404296875,
    0.0443115234375,
    -0.01090240478515625,
    0.0001710653305053711,
    -0.00438690185546875,
    -0.0197601318359375,
    -0.0057373046875,
    -0.04656982421875,
    0.0457763671875,
    -0.0038967132568359375,
    0.0201263427734375,
    -0.025634765625,
    -0.0285797119140625,
    -0.01495361328125,
    -0.0187530517578125,
    0.004932403564453125,
    -0.03704833984375,
    -0.021881103515625,
    -0.00443267822265625,
    0.050079345703125,
    -0.0234222412109375,
    -0.041015625,
    -0.0020008087158203125,
    0.0225982666015625,
    -0.01329803466796875,
    0.005615234375,
    0.00846099853515625,
    0.01198577880859375,
    0.08660888671875,
    0.006465911865234375,
    -0.0240936279296875,
    0.054229736328125,
    0.0218658447265625,
    0.025390625,
    0.0302581787109375,
    -0.022308349609375,
    -0.022796630859375,
    -0.00492095947265625,
    0.034759521484375,
    -0.0343017578125,
    -0.0025196075439453125,
    0.024810791015625,
    0.006778717041015625,
    -0.0091400146484375,
    0.00923919677734375,
    0.014495849609375,
    -0.007511138916015625,
    -0.017669677734375,
    -0.0067901611328125,
    0.01125335693359375,
    0.0214691162109375,
    0.002185821533203125,
    0.0233001708984375,
    0.0116424560546875,
    0.01629638671875,
    -0.01415252685546875,
    0.002521514892578125,
    0.0323486328125,
    -0.036712646484375,
    -0.0288848876953125,
    0.0283203125,
    0.04400634765625,
    0.02569580078125,
    0.007747650146484375,
    -0.0095977783203125,
    0.02105712890625,
    0.0217132568359375,
    0.0131378173828125,
    0.0082855224609375,
    0.033050537109375,
    0.0372314453125,
    0.01142120361328125,
    -0.0052490234375,
    -0.014129638671875,
    -0.0006322860717773438,
    0.01302337646484375,
    0.01345062255859375,
    -0.021942138671875,
    0.0028209686279296875,
    -0.0030956268310546875,
    0.01493072509765625,
    0.002201080322265625,
    -0.0024127960205078125,
    -0.01031494140625,
    -0.030181884765625,
    0.028045654296875,
    0.01123809814453125,
    0.0175628662109375,
    0.008941650390625,
    0.0177001953125,
    0.00763702392578125,
    -0.02728271484375,
    -0.04229736328125,
    -0.0277252197265625,
    -0.0232696533203125,
    -0.005809783935546875,
    -0.053802490234375,
    -0.00530242919921875,
    -0.0200347900390625,
    0.05718994140625,
    -0.0003597736358642578,
    -0.023956298828125,
    0.002269744873046875,
    -0.0218505859375,
    -0.304443359375,
    0.012786865234375,
    -0.006744384765625,
    0.0285491943359375,
    -0.035858154296875,
    -0.00884246826171875,
    -0.007843017578125,
    -0.04827880859375,
    -0.034912109375,
    -0.0218658447265625,
    -0.0174102783203125,
    -0.050079345703125,
    -0.055908203125,
    -0.01120758056640625,
    -0.00421905517578125,
    -0.005802154541015625,
    0.01055145263671875,
    -0.034210205078125,
    0.0224456787109375,
    -0.038055419921875,
    -0.0230255126953125,
    -0.035308837890625,
    0.03472900390625,
    0.0014858245849609375,
    0.0017232894897460938,
    0.0105438232421875,
    0.01306915283203125,
    0.01409149169921875,
    -0.032867431640625,
    -0.02392578125,
    0.0229034423828125,
    -0.0108489990234375,
    -0.01361846923828125,
    0.036041259765625,
    0.056793212890625,
    0.0229034423828125,
    0.01375579833984375,
    -0.011138916015625,
    0.037139892578125,
    0.0132904052734375,
    -0.005706787109375,
    0.027740478515625,
    0.0013265609741210938,
    -0.002368927001953125,
    0.0025043487548828125,
    -0.0369873046875,
    -0.0017719268798828125,
    -0.0211181640625,
    0.025299072265625,
    -0.0285797119140625,
    0.01593017578125,
    0.0034275054931640625,
    0.03216552734375,
    -0.03338623046875,
    -0.03387451171875,
    0.00848388671875,
    0.0032901763916015625,
    0.057952880859375,
    0.035369873046875,
    -0.00505828857421875,
    -0.00643157958984375,
    -0.04376220703125,
    0.0049896240234375,
    0.023162841796875,
    0.01555633544921875,
    0.0120086669921875,
    -0.00022161006927490234,
    0.0211639404296875,
    -0.01457977294921875,
    -0.012359619140625,
    0.038818359375,
    0.0181732177734375,
    0.01220703125,
    -0.025421142578125,
    0.023162841796875,
    0.05029296875,
    -0.033538818359375,
    -0.0258636474609375,
    -0.023223876953125,
    -0.160400390625,
    -0.004730224609375,
    0.0204925537109375,
    0.0111846923828125,
    0.01218414306640625,
    -0.04541015625,
    -0.031463623046875,
    0.00628662109375,
    0.0133514404296875,
    0.033782958984375,
    0.40673828125,
    0.01268768310546875,
    0.0299530029296875,
    -0.019561767578125,
    0.032196044921875,
    -0.028350830078125,
    0.005870819091796875,
    -0.0162353515625,
    0.018951416015625,
    -0.029296875,
    -0.033843994140625,
    -0.002902984619140625,
    0.0231170654296875,
    -0.003688812255859375,
    -0.007671356201171875,
    0.030181884765625,
    -0.035736083984375,
    0.00504302978515625,
    0.0777587890625,
    -0.006103515625,
    0.022552490234375,
    -0.01203155517578125,
    0.005474090576171875,
    0.0044403076171875,
    -0.005340576171875,
    -0.05218505859375,
    -0.006481170654296875,
    0.058258056640625,
    -0.037078857421875,
    0.005214691162109375,
    -0.0657958984375,
    -0.006511688232421875,
    0.029296875,
    -0.0015888214111328125,
    0.004184722900390625,
    -0.00902557373046875,
    -0.005157470703125,
    -0.01953125,
    0.0119781494140625,
    0.01284027099609375,
    -0.00199127197265625,
    -0.048614501953125,
    0.0247650146484375,
    0.00624847412109375,
    0.0181732177734375,
    -0.03167724609375,
    -0.0135650634765625,
    -0.004913330078125,
    -0.010467529296875,
    -0.0228271484375,
    -0.004730224609375,
    0.02032470703125,
    -0.0204315185546875,
    0.006946563720703125,
    -0.0093231201171875,
    -0.019256591796875,
    -0.0030002593994140625,
    -0.005092620849609375,
    -0.013153076171875,
    0.0017261505126953125,
    0.04241943359375,
    -0.007511138916015625,
    -0.01520538330078125,
    -0.024261474609375,
    -0.007568359375,
    0.0305328369140625,
    -0.0177001953125,
    -0.030059814453125,
    0.01006317138671875,
    0.0253448486328125,
    0.023162841796875,
    -0.032470703125,
    0.0014581680297851562,
    0.007656097412109375,
    0.06695556640625,
    0.03887939453125,
    -0.0128021240234375,
    0.058929443359375,
    0.037322998046875,
    0.0176544189453125,
    -0.0214080810546875,
    0.002780914306640625,
    -0.06646728515625,
    0.008087158203125,
    0.024169921875,
    0.0182037353515625,
    0.0196533203125,
    0.00959014892578125,
    -0.020965576171875,
    -0.029510498046875,
    0.02020263671875,
    0.00977325439453125,
    -0.039520263671875,
    0.015777587890625,
    0.00482177734375,
    -0.006622314453125,
    0.012451171875,
    -0.007701873779296875,
    -0.0411376953125,
    0.02203369140625,
    -0.019561767578125,
    -0.01520538330078125,
    -0.0158843994140625,
    -0.0166015625,
    0.030303955078125,
    -0.01580810546875,
    -0.01331329345703125,
    0.0214385986328125,
    -0.019927978515625,
    0.033721923828125,
    -0.0075225830078125,
    0.00490570068359375,
    -0.019439697265625,
    -0.0253753662109375,
    0.0191802978515625,
    0.0205535888671875,
    0.0006275177001953125,
    0.00531768798828125,
    0.032745361328125,
    0.049957275390625,
    -0.030548095703125,
    -0.017303466796875,
    0.0019311904907226562,
    0.0137176513671875,
    -0.005031585693359375,
    0.00708770751953125,
    -0.018280029296875,
    0.02239990234375,
    -0.0396728515625,
    0.038787841796875,
    0.00923919677734375,
    -0.027191162109375,
    -0.0175933837890625,
    0.019012451171875,
    0.0478515625,
    0.0034618377685546875,
    0.0282745361328125,
    0.024810791015625,
    -0.002422332763671875,
    0.044464111328125,
    0.015380859375,
    0.0038242340087890625,
    -0.0011539459228515625,
    0.0185394287109375,
    -0.00209808349609375,
    -0.01953125,
    -0.00925445556640625,
    -0.014007568359375,
    -0.0048980712890625,
    -0.01505279541015625,
    -0.0174560546875,
    0.03521728515625,
    -0.017547607421875,
    -0.045318603515625,
    -0.00284576416015625,
    -0.0012111663818359375,
    -0.036865234375,
    -0.0207061767578125,
    0.015472412109375,
    -0.0279998779296875,
    0.0239105224609375,
    0.0115966796875,
    0.01554107666015625,
    0.118408203125,
    0.023284912109375,
    0.044586181640625,
    -0.06475830078125,
    0.0428466796875,
    0.0179595947265625,
    -0.0217742919921875,
    0.021514892578125,
    -0.0131378173828125,
    -0.063232421875,
    0.0186767578125,
    0.04241943359375,
    0.024932861328125,
    -0.03802490234375,
    0.0010471343994140625,
    -0.00818634033203125,
    0.0239105224609375,
    0.0260162353515625,
    0.024261474609375,
    0.0222320556640625,
    0.0146484375,
    0.01007080078125,
    0.03558349609375,
    0.01509857177734375,
    -0.0311279296875,
    0.0185699462890625,
    -0.0207061767578125,
    -0.030487060546875,
    0.110595703125,
    0.01456451416015625,
    -0.0279693603515625,
    0.027069091796875,
    0.0013217926025390625,
    -0.0161895751953125,
    0.040069580078125,
    0.025482177734375,
    -0.01129913330078125,
    0.01904296875,
    0.004299163818359375,
    0.0134429931640625,
    -0.00943756103515625,
    0.0065460205078125,
    -0.01010894775390625,
    -0.04254150390625,
    0.0093994140625,
    -0.00228118896484375,
    0.0034885406494140625,
    -0.00634765625,
    0.016571044921875,
    0.00847625732421875,
    0.0186767578125,
    0.01100921630859375,
    0.0241851806640625,
    -0.0083465576171875,
    0.01346588134765625,
    -0.0034046173095703125,
    -0.0274200439453125,
    -0.0009250640869140625,
    0.00923919677734375,
    0.041229248046875,
    -0.053863525390625,
    -0.004367828369140625,
    0.002368927001953125,
    -0.0028228759765625,
    -0.0265960693359375,
    0.01331329345703125,
    0.0200958251953125,
    0.0204010009765625,
    0.01202392578125,
    -0.0018968582153320312,
    -0.00643157958984375,
    0.010009765625,
    -5.221366882324219e-05,
    -0.0157012939453125,
    0.007293701171875,
    0.0178680419921875,
    -0.0001232624053955078,
    0.0240478515625,
    -0.0290679931640625,
    0.0207977294921875,
    0.033294677734375,
    -0.0027027130126953125,
    0.0282135009765625,
    0.00921630859375,
    0.0236968994140625,
    0.04034423828125,
    0.0457763671875,
    0.005336761474609375,
    -0.0019330978393554688,
    0.0157928466796875,
    -0.03076171875,
    -0.01300048828125,
    0.01432037353515625,
    -0.0216064453125,
    -0.00360107421875,
    -0.053985595703125,
    0.005336761474609375,
    -0.03472900390625,
    0.00365447998046875,
    -0.03436279296875,
    0.00272369384765625,
    -0.00926971435546875,
    -0.031585693359375,
    0.04803466796875,
    0.00943756103515625,
    -0.01531982421875,
    -0.043914794921875,
    0.008270263671875,
    -0.031524658203125,
    -0.05426025390625,
    -0.01206207275390625,
    0.02801513671875,
    0.0195465087890625,
    -0.02105712890625,
    -0.009368896484375,
    0.0036792755126953125,
    0.02154541015625,
    0.0140533447265625,
    0.019561767578125,
    0.0034332275390625,
    0.0218048095703125,
    -0.02532958984375,
    0.0010461807250976562,
    0.0243072509765625,
    0.00846099853515625,
    -0.0180816650390625,
    -0.03472900390625,
    -0.013092041015625,
    -0.0128936767578125,
    -0.034942626953125,
    0.02215576171875,
    -0.0011730194091796875,
    0.018524169921875,
    -0.046295166015625,
    0.00727081298828125,
    -0.03369140625,
    0.00872802734375,
    -0.055908203125,
    0.0233917236328125,
    -0.0506591796875,
    -0.0252838134765625,
    -0.00899505615234375,
    0.01268768310546875,
    -0.007579803466796875,
    -0.0484619140625,
    0.006267547607421875,
    0.01904296875,
    0.01126861572265625,
    -0.0189208984375,
    0.0004744529724121094,
    0.022369384765625,
    0.0015306472778320312,
    -0.0019683837890625,
    0.040283203125,
    -0.03173828125,
    -0.014129638671875,
    0.0018444061279296875,
    0.00469207763671875,
    -0.0010156631469726562,
    -0.00688934326171875,
    -0.01302337646484375,
    -0.004283905029296875,
    0.00328826904296875,
    0.0033626556396484375,
    0.0017805099487304688,
    -0.039947509765625,
    -0.00438690185546875,
    -0.043182373046875,
    0.03485107421875,
    -0.0024280548095703125,
    -0.020538330078125,
    -0.006855010986328125,
    0.00836181640625,
    -0.006267547607421875,
    -0.034912109375,
    0.048797607421875,
    -0.01812744140625,
    0.005954742431640625,
    0.0024242401123046875,
    0.04522705078125,
    -0.042694091796875,
    0.0171051025390625,
    -0.0433349609375,
    0.0080413818359375,
    -0.006053924560546875,
    -0.0122222900390625,
    0.01678466796875,
    -0.004177093505859375,
    0.05841064453125,
    -0.01230621337890625,
    -0.042266845703125,
    0.00240325927734375,
    -0.0012388229370117188,
    -0.051483154296875,
    -0.0135955810546875,
    0.0244903564453125,
    0.0135345458984375,
    -0.013641357421875,
    0.0121307373046875,
    0.0035552978515625,
    0.04461669921875,
    -0.0034732818603515625,
    0.027862548828125,
    0.034820556640625,
    -0.0123748779296875,
    0.02008056640625,
    -0.0239105224609375,
    0.0015134811401367188,
    0.01959228515625,
    -0.0228118896484375,
    0.02752685546875,
    -0.0126953125,
    0.0303192138671875,
    -0.0087432861328125,
    -0.0262603759765625,
    0.03094482421875,
    -0.001132965087890625,
    -0.01502227783203125,
    -0.033935546875,
    -0.04681396484375,
    -0.0582275390625,
    0.027374267578125,
    0.005767822265625,
    0.0188446044921875,
    -0.01395416259765625,
    0.03350830078125,
    -0.00583648681640625,
    -0.0478515625,
    -0.01439666748046875,
    -0.044647216796875,
    0.021820068359375,
    -0.2044677734375,
    -0.0034236907958984375,
    0.004425048828125,
    -0.01123046875,
    -0.062408447265625,
    -0.0279083251953125,
    -0.036956787109375,
    0.00983428955078125,
    -0.0045013427734375,
    -0.0163726806640625,
    -0.0261383056640625,
    0.018707275390625,
    0.010772705078125,
    -0.0250244140625,
    -0.005916595458984375,
    0.039886474609375,
    0.019500732421875,
    -0.004062652587890625,
    -0.00399017333984375,
    0.0019741058349609375,
    -0.0089874267578125,
    0.0070037841796875,
    0.0183563232421875,
    0.007190704345703125,
    0.002941131591796875,
    -0.012359619140625,
    -0.0033550262451171875,
    0.01026153564453125,
    -0.04583740234375,
    -0.0189971923828125,
    0.0027523040771484375,
    -0.0174407958984375,
    0.044647216796875,
    0.023956298828125,
    -0.004741668701171875,
    -0.001800537109375,
    -0.01427459716796875,
    -0.0048980712890625,
    0.015289306640625,
    0.0012569427490234375,
    -0.00337982177734375,
    0.03961181640625,
    0.0036296844482421875,
    -0.01409149169921875,
    0.006893157958984375,
    0.0135345458984375,
    0.0002906322479248047,
    -0.0004520416259765625,
    -0.03094482421875,
    -0.01374053955078125,
    0.0007901191711425781,
    -0.0036563873291015625,
    -0.009429931640625,
    0.00911712646484375,
    -0.012176513671875,
    0.03125,
    -0.048736572265625,
    0.01262664794921875,
    0.032318115234375,
    0.061248779296875,
    0.0128631591796875,
    -0.00708770751953125,
    -0.0233001708984375,
    -0.02569580078125,
    -0.0283050537109375,
    -0.0110931396484375,
    -0.042510986328125,
    0.0181884765625,
    0.023284912109375,
    -0.009765625,
    -0.027679443359375,
    -0.01145172119140625,
    0.004497528076171875,
    -0.036102294921875,
    0.018707275390625,
    0.035980224609375,
    0.035186767578125,
    -0.0124053955078125,
    -0.009124755859375,
    -0.00537109375,
    0.017791748046875,
    0.01035308837890625,
    -0.0104522705078125,
    -0.004261016845703125,
    0.01473236083984375,
    0.0171356201171875,
    -0.0244903564453125,
    0.00539398193359375,
    -0.0158538818359375,
    0.01132965087890625,
    -0.04736328125,
    -0.0357666015625,
    -0.0029315948486328125,
    -0.024810791015625,
    -0.055145263671875,
    -0.009429931640625,
    -0.0065460205078125,
    -0.0092315673828125,
    -0.045806884765625,
    -0.007076263427734375,
    -0.037811279296875,
    -0.0267486572265625,
    -0.00954437255859375,
    -0.020751953125,
    -0.0291290283203125,
    0.034759521484375,
    0.034515380859375,
    -0.02154541015625,
    0.007236480712890625,
    -0.002727508544921875,
    -0.00504302978515625,
    -0.005489349365234375,
    -0.005825042724609375,
    -0.0228271484375,
    -0.03125,
    0.01153564453125,
    -0.0117034912109375,
    -0.005687713623046875,
    -0.031280517578125,
    -0.005878448486328125,
    -0.01210784912109375,
    0.01143646240234375,
    -0.01378631591796875,
    -0.03802490234375,
    -0.00046944618225097656,
    -0.014495849609375,
    0.01021575927734375,
    0.0003190040588378906,
    0.0186004638671875,
    -0.0169677734375,
    0.0340576171875,
    -0.03729248046875,
    -0.01407623291015625,
    0.0269927978515625,
    0.0205841064453125,
    -0.030670166015625,
    -0.0118255615234375,
    0.040802001953125,
    -0.0249481201171875,
    -0.054962158203125,
    -0.01305389404296875,
    0.0233917236328125,
    -0.0309906005859375,
    -0.0131378173828125,
    -0.01427459716796875,
    -0.009979248046875,
    0.01100921630859375,
    0.0003638267517089844,
    -0.04833984375,
    -0.0281829833984375,
    0.04461669921875,
    -0.0023555755615234375,
    -0.0020771026611328125,
    0.006336212158203125,
    -0.0031108856201171875,
    -0.0076141357421875,
    -0.026763916015625,
    -0.01122283935546875,
    0.018890380859375,
    0.01922607421875,
    0.0214385986328125,
    -0.039093017578125,
    -0.0136260986328125,
    -0.026214599609375,
    0.0017976760864257812,
    -0.0027103424072265625,
    -0.0004029273986816406,
    0.01453399658203125,
    0.00030303001403808594,
    -0.004467010498046875,
    -0.01983642578125,
    0.022369384765625,
    -0.048248291015625,
    0.038848876953125,
    0.023590087890625,
    -0.0186614990234375,
    0.01297760009765625,
    0.0164337158203125,
    0.04547119140625,
    0.010986328125,
    0.0211944580078125,
    0.045623779296875,
    0.032379150390625,
    0.01153564453125,
    -0.00203704833984375,
    0.04901123046875,
    -0.0020771026611328125,
    0.0307159423828125,
    0.0035610198974609375,
    -0.0009713172912597656,
    -0.01247406005859375,
    -0.004436492919921875,
    0.016326904296875,
    -0.029571533203125,
    0.0277252197265625,
    -0.005825042724609375,
    0.02362060546875,
    0.056549072265625,
    -0.03289794921875,
    0.0665283203125,
    -0.00799560546875,
    -0.038116455078125,
    -0.0286407470703125,
    -0.0285491943359375,
    -0.00846099853515625,
    0.0022640228271484375,
    -0.0029144287109375,
    -0.0238800048828125,
    -0.0279541015625,
    0.007781982421875,
    -0.0012197494506835938,
    -0.0154876708984375,
    -0.01448822021484375,
    0.03558349609375,
    -0.0011606216430664062,
    0.00852203369140625,
    0.016326904296875,
    0.01165771484375,
    0.0216217041015625,
    -0.00420379638671875,
    -0.0044708251953125,
    0.0174713134765625,
    -0.0411376953125,
    0.005207061767578125,
    0.0225830078125,
    -0.0211181640625,
    -0.01407623291015625,
    0.01482391357421875,
    -0.0229644775390625,
    -0.04931640625,
    0.0090179443359375,
    -0.015472412109375,
    -0.036956787109375,
    0.070068359375,
    0.02288818359375,
    0.0032291412353515625,
    0.043365478515625,
    0.05389404296875,
    0.009368896484375,
    -0.019989013671875,
    0.044647216796875,
    -0.0063934326171875,
    -0.0264892578125,
    0.0019817352294921875,
]


@get_driver().on_startup
async def _():
    global img_model
    if img_model:
        return
    img_model = ViTnLPE(
        heads=16,
        input_resolution=224,
        layers=24,
        output_dim=1024,
        patch_size=14,
        width=1024,
    )
    img_model.load_state_dict(
        torch.load(
            plugin_config.p_model_path,
            map_location=torch.device("cpu"),
            weights_only=True,
        )
    )
    img_model.to(torch.bfloat16)
    img_model.eval()
    logger.info(
        "ViTnLPE model loaded, input resolution: 224x224, patch size: 14x14, width: 1024, heads: 16, layers: 24, output dim: 1024"
    )


__t = transforms.Compose(
    [
        lambda x: x.convert("RGB"),
        transforms.Resize((224, 224), transforms.InterpolationMode.BICUBIC),
        transforms.ToTensor(),
        transforms.Normalize(
            (0.48145466, 0.4578275, 0.40821073),
            (0.26862954, 0.26130258, 0.27577711),
        ),
    ]
)


async def word2vec(word: str) -> list[float]:
    if not word:
        return NULL_EMB
    try:
        return (
            (
                await CLIENT.embeddings.create(
                    input=word, model=plugin_config.embedding_model
                )
            )
            .data[0]
            .embedding
        )
    except Exception as e:
        logger.error(f"Error while embedding word: {word}, {e}")
        return NULL_EMB


async def img2vec(img: bytes, title: str = "") -> list | None:
    """1024 D"""
    global plugin_config, __t, img_model
    if not plugin_config.simpic_model:
        return None
    if plugin_config.simpic_model not in ["ViT/16-Bfloat16-Modify"]:
        raise NotImplementedError(f"Unsupported model: {plugin_config.simpic_model}")
    return (
        await asyncio.to_thread(
            img_model,
            __t(Image.open(BytesIO(img))).to(torch.bfloat16).unsqueeze(0),
            torch.Tensor(np.array(await word2vec(title)))
            .to(torch.bfloat16)
            .unsqueeze(0),
        )
    ).tolist()[0]


async def ocr(img: bytes) -> str:
    prompt = """Your response should be in the following format:
```
{
    "text": "The text detected in the image.",
    "score": "The confidence score of the text detection."
}

If the text detection fails, return an empty string.
```
{
    "text": "",
    "score": 0.0
}
```"""

    ret = (
        (
            await CLIENT.chat.completions.create(
                model=plugin_config.ocr_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "OCR:"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64.b64encode(img).decode()}"
                                },
                            },
                        ],
                    },
                ],
            )
        )
        .choices[0]
        .message.content
    )
    try:
        return json.loads(ret.split("```")[1].split("```")[0].strip("`").strip("json"))
    except Exception:
        logger.error(f"OCR error: {ret}")
        return {}