

from PIL import Image
import numpy as np
import torch
import torchvision
import torch.nn as nn
from typing import Type, Any, Callable, Union, List, Optional
import os
import cv2


def conv3x3(in_planes: int, out_planes: int, stride: int = 1, groups: int = 1, dilation: int = 1) -> nn.Conv2d:
    """3x3 convolution with padding"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
                     padding=dilation, groups=groups, bias=False, dilation=dilation)


def conv1x1(in_planes: int, out_planes: int, stride: int = 1) -> nn.Conv2d:
    """1x1 convolution"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=1, stride=stride, bias=False)

class BasicBlock(nn.Module):
    expansion: int = 1

    def __init__(self, inplanes: int, planes: int, stride: int = 1, downsample: Optional[nn.Module] = None,
                 groups: int = 1, base_width: int = 64, dilation: int = 1, norm_layer: Optional[Callable[..., nn.Module]] = None) -> None:
        
        super(BasicBlock, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        if groups != 1 or base_width != 64:
            raise ValueError('BasicBlock only supports groups=1 and base_width=64')
        if dilation > 1:
            raise NotImplementedError("Dilation > 1 not supported in BasicBlock")
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = norm_layer(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = norm_layer(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out


class ResNet(nn.Module):

    def __init__(self, layers: List[int], init_features, num_classes: int = 1000, zero_init_residual: bool = False, groups: int = 1, width_per_group: int = 64,
                 replace_stride_with_dilation: Optional[List[bool]] = None, norm_layer: Optional[Callable[..., nn.Module]] = None) -> None:
        super(ResNet, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        self._norm_layer = norm_layer
        block = BasicBlock 
        self.inplanes = init_features
        self.dilation = 1
        if replace_stride_with_dilation is None:
            # each element in the tuple indicates if we should replace
            # the 2x2 stride with a dilated convolution instead
            replace_stride_with_dilation = [False, False, False]
        if len(replace_stride_with_dilation) != 3:
            raise ValueError("replace_stride_with_dilation should be None "
                             "or a 3-element tuple, got {}".format(replace_stride_with_dilation))
        self.groups = groups
        self.base_width = width_per_group
        self.conv1 = nn.Conv2d(3, self.inplanes, kernel_size=7, stride=2, padding=3,
                               bias=False)
        self.bn1 = norm_layer(self.inplanes)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, init_features, layers[0])
        self.layer2 = self._make_layer(block, init_features*2, layers[1], stride=2,
                                       dilate=replace_stride_with_dilation[0])
        self.layer3 = self._make_layer(block, init_features*4, layers[2], stride=2,
                                       dilate=replace_stride_with_dilation[1])
        self.layer4 = self._make_layer(block, init_features*8, layers[3], stride=2,
                                       dilate=replace_stride_with_dilation[2])
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(init_features*8 * block.expansion, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

        # Zero-initialize the last BN in each residual branch,
        # so that the residual branch starts with zeros, and each residual block behaves like an identity.
        # This improves the model by 0.2~0.3% according to https://arxiv.org/abs/1706.02677
        if zero_init_residual:
            for m in self.modules():
                nn.init.constant_(m.bn2.weight, 0)  # type: ignore[arg-type]

    def _make_layer(self, block, planes: int, blocks: int,
                    stride: int = 1, dilate: bool = False) -> nn.Sequential:
        norm_layer = self._norm_layer
        downsample = None
        previous_dilation = self.dilation
        if dilate:
            self.dilation *= stride
            stride = 1
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                conv1x1(self.inplanes, planes * block.expansion, stride),
                norm_layer(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample, self.groups,
                            self.base_width, previous_dilation, norm_layer))
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes, groups=self.groups,
                                base_width=self.base_width, dilation=self.dilation,
                                norm_layer=norm_layer))

        return nn.Sequential(*layers)

    def _forward_impl(self, x: torch.Tensor) -> torch.Tensor:
        # See note [TorchScript super()]
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)

        return x

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self._forward_impl(x)

def resnet18(num_classes, init_features= 64, **kwargs: Any):
    return ResNet([2, 2, 2, 2], init_features=init_features, num_classes=num_classes, **kwargs)

def resnet34(num_classes, init_features= 64, **kwargs: Any):
    return ResNet([3, 4, 6, 3], init_features=init_features, num_classes=num_classes, **kwargs)
 

classes= ["xray","stehend","vornuebergebeugt"]
norm_stats = ([0.485, 0.456, 0.406],[0.229, 0.224, 0.225])
model_file="model.pth"
img_size=(512,512)


class PYTORCH_CONTEXT:
    def __init__(self, model, state_dict_file, norm_stats_mean, norm_stats_std, device="cpu"):
        self.model = model
        self.model.load_state_dict(torch.load(state_dict_file, map_location=torch.device(device))["model"])
        self.model = self.model.eval()
        self.normalize = torchvision.transforms.Normalize(norm_stats_mean,norm_stats_std)
        self.to_tensor = torchvision.transforms.ToTensor() 
    
    def inference(self, inp):
                
        net_inp = self.normalize(self.to_tensor(inp))[None]
        with torch.no_grad():
            out = self.model(net_inp)
        return np.squeeze(np.array(out))

class MLProcessModel:
    type=''
    context=None
    resultdir=''

    def __init__(self, type='categorize_img', mlmodeldir='.',ssm=None):
        print('Changing current working dir to: ',mlmodeldir)
        os.chdir(mlmodeldir)
        print('Current working Directory: ',os.getcwd())
        self.type=type
        resnet = resnet18(init_features=16,num_classes=3)
        self.context =PYTORCH_CONTEXT(model = resnet,state_dict_file=model_file,norm_stats_mean=norm_stats[0],
                                        norm_stats_std=norm_stats[1])
        self.resultdir = mlmodeldir + 'results/'
        self.ssm = ssm

    def inference(self, img=None):
        if img is None:
            print('No image.')
            return
        
        if self.context is None:
            print("No model loaded.")
            return
            
        out = self.context.inference(Image.open(open(img,"rb")).convert("RGB").resize(img_size))
        out_class = classes[np.argmax(out)]
        confidence = np.max(out)
        imgname = self.label_img(img, out_class, confidence)
            
        print(out_class, confidence, imgname)
        return out_class, confidence, imgname 

    def label_img(self, img, prediction, performance):
        image = cv2.resize(cv2.imread(img), img_size)
        # assign a new name identifier to the modified image - so that it does not interfere with other images
        if self.ssm:
            imgname = 'modified_' + str(self.ssm) + '.jpg'
        else:
            imgname = img.rsplit('/')[-1]

        # Schreiben des Images
        w = image.shape[0]
        h = image.shape[1]
        heatmap = np.zeros((w, h), dtype=np.uint8)
        cv2.putText(image, prediction, (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1,(255, 128, 128), lineType=cv2.LINE_AA)

        # Scale
        image[h-10:h,:,:]=np.zeros((10,w,3), dtype=np.uint8)
        for i in range(w):
            c = int(i / w * 255)
            cv2.line(heatmap, (i, h - 10), (i, h), c)
        im3 = cv2.applyColorMap(heatmap, cv2.COLORMAP_RAINBOW)
        target_img = image + im3
        cv2.imwrite(self.resultdir + imgname, target_img)
        print('Write image to %s' % (self.resultdir + imgname))
        return imgname

'''
def main():
    model = MLProcessModel()
    print(model.inference("3HANRK5A_sized_0.0.png"))

if __name__ == "__main__":
    main()
'''