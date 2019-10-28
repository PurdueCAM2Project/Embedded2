from __future__ import print_function
import os
import sys
#os.environ["CUDA_VISIBLE_DEVICES"] = "0,1,2,3,4,5,6,7"
import torch
import torch.optim as optim
import torch.backends.cudnn as cudnn
import argparse
from torch.autograd import Variable
import torch.utils.data as data
from data_mobilenet import AnnotationTransform, VOCDetection, detection_collate, preproc_s3fd
from data_mobilenet.config_s3fd_mv2 import cfg
from layers_mobilenet.modules.multibox_loss_s3fd import MultiBoxLoss
from layers_mobilenet.functions.prior_box_s3fd import PriorBox
import time
import math
from models_mobilenet.s3fd import S3FD, S3FD_MV2#, S3FD_FairNAS_A, S3FD_FairNAS_B
# from models.s3fd_resnet import S3FD_RESNET18
from utils_mobilenet.logging import Logger
from utils_mobilenet.logging import TensorboardSummary

parser = argparse.ArgumentParser(description='S3FD Training')
parser.add_argument('--training_dataset', default='./data/WIDER_FACE', help='Training dataset directory')
parser.add_argument('-b', '--batch_size', default=4, type=int, help='Batch size for training') #changed from 32 to 4 (Arnav)
parser.add_argument('--num_workers', default=2, type=int, help='Number of workers used in dataloading') #changed from 16 to 2 (Arnav)
parser.add_argument('--cuda', default=True, type=bool, help='Use cuda to train model')
parser.add_argument('--ngpu', default=1, type=int, help='gpus')
parser.add_argument('--lr', '--learning-rate', default=1e-3, type=float, help='initial learning rate')
parser.add_argument('--momentum', default=0.9, type=float, help='momentum')
parser.add_argument('--resume_net', default=None, help='resume net for retraining')
parser.add_argument('--resume_epoch', default=0, type=int, help='resume iter for retraining')
parser.add_argument('-max', '--max_epoch', default=2, type=int, help='max epoch for retraining') #changed from 300 to 2 (Arnav)
parser.add_argument('--net', default='mv2', help='backone network')
parser.add_argument('--weight_decay', default=5e-4, type=float, help='Weight decay for SGD')
parser.add_argument('--gamma', default=0.1, type=float, help='Gamma update for SGD')
parser.add_argument('--save_folder', default='./weights/mobilenet_weight', help='Location to save checkpoint models')
parser.add_argument('--pretrained', default='./weights/vgg16_reducedfc.pth', help='Location to save checkpoint models')
args = parser.parse_args()

if not os.path.exists(args.save_folder):
    os.mkdir(args.save_folder)

# Logger
sys.stdout = Logger(os.path.join(args.save_folder, 'log.txt'))
# TensorBoardX
summary = TensorboardSummary(args.save_folder)
writer = summary.create_summary()

img_dim = 640 #changed to 300 from 640 (Arnav)
# rgb_means = (104, 117, 123)
rgb_means = (123, 117, 104)
num_classes = 2
batch_size = args.batch_size
weight_decay = args.weight_decay
gamma = args.gamma
momentum = args.momentum
if args.net == 'mv2':
    net = S3FD_MV2('train', img_dim, num_classes)
# elif args.net == 'vgg16':
#     net = S3FD('train', img_dim, num_classes)
# elif args.net == 'FairNAS_A':
#     net = S3FD_FairNAS_A('train', img_dim, num_classes)
# elif args.net == 'FairNAS_B':
#     net = S3FD_FairNAS_B('train', img_dim, num_classes)
# elif args.net == 'resnet18':
#     net = S3FD_RESNET18('train', img_dim, num_classes)
print("Printing net...")
print(net)

'''if os.path.isfile(args.pretrained):
    vgg_weights = torch.load(args.pretrained)
    print('Loading VGG network...')
    net.vgg.load_state_dict(vgg_weights)'''

if args.resume_net is not None:
    print('Loading resume network...')
    state_dict = torch.load(args.resume_net)
    # create new OrderedDict that does not contain `module.`
    from collections import OrderedDict
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        head = k[:7]
        if head == 'module.':
            name = k[7:] # remove `module.`
        else:
            name = k
        new_state_dict[name] = v
    net.load_state_dict(new_state_dict)
elif os.path.isfile(args.pretrained):
    # vgg_weights = torch.load(args.pretrained)
    vgg_weights = torch.load(args.pretrained, map_location=lambda storage, loc: storage)
    if args.net == 'vgg16':
        print('Loading VGG network...')
        net.vgg.load_state_dict(vgg_weights)
    elif args.net == 'resnet18':
        net.base.load_state_dict(vgg_weights)
    elif args.net == 'mv2':
        print('Loading MobileNet V2 network...')
        model_dict = net.base_net.state_dict()    
        # for k in vgg_weights['net'].keys():
        #     model_dict[k.replace('module.features.', '')] = vgg_weights['net'][k]
        for k in vgg_weights.keys():
            # print("key: ", vgg_weights[k], "\n")
            model_dict[k.replace('module.features.', '')] = vgg_weights[k]
        net.base_net.load_state_dict(model_dict, strict=False)
    elif args.net == 'FairNAS_A':
        print('Loading FairNAS_A network...')
        model_dict = net.base_net.state_dict()
        f_key = open("./weights/fairnas_a_model_key.txt", 'r')
        if f_key is None:
            exit()
        else:
            model_keys = f_key.readlines()
        f_key.close()

        f_key = open("./weights/fairnas_a_ckpt_key.txt", 'r')
        if f_key is None:
            exit()
        else:
            ckpt_keys = f_key.readlines()
        f_key.close()

        for idx, key in enumerate(model_keys):
            # print(key.strip('\n'), ckpt_keys[idx].strip('\n'))
            model_dict[key.strip('\n')] = vgg_weights['model_state'][ckpt_keys[idx].strip('\n')]
        net.base_net.load_state_dict(model_dict, strict=False)
    elif args.net == 'FairNAS_B':
        print('Loading FairNAS_B network...')
        model_dict = net.base_net.state_dict()
        f_key = open("./weights/fairnas_b_model_key.txt", 'r')
        if f_key is None:
            exit()
        else:
            model_keys = f_key.readlines()
        f_key.close()

        f_key = open("./weights/fairnas_b_ckpt_key.txt", 'r')
        if f_key is None:
            exit()
        else:
            ckpt_keys = f_key.readlines()
        f_key.close()

        for idx, key in enumerate(model_keys):
            # print(key.strip('\n'), ckpt_keys[idx].strip('\n'))
            model_dict[key.strip('\n')] = vgg_weights['model_state'][ckpt_keys[idx].strip('\n')]
        # for k in model_dict.keys():
        #   print(k)
        # for k in checkpoint['model_state'].keys():
        #   print(k)
        # for k in checkpoint['net'].keys():
        #     model_dict[k.replace('module.features.', '')] = checkpoint['net'][k]
        net.base_net.load_state_dict(model_dict, strict=False)

if args.ngpu > 1:
    net = torch.nn.DataParallel(net, device_ids=list(range(args.ngpu)))

if args.cuda:
    net.cuda()
    cudnn.benchmark = True

optimizer = optim.SGD(net.parameters(), lr=args.lr, momentum=args.momentum, weight_decay=args.weight_decay)
criterion = MultiBoxLoss(num_classes, (0.5, 0.35, 0.1), True, 0, True, 3, 0.35, False)

priorbox = PriorBox(cfg)
with torch.no_grad():
    priors = priorbox.forward()
    if args.cuda:
        priors = priors.cuda()


def train():
    net.train()
    epoch = 0 + args.resume_epoch
    print('Loading Dataset...')

    dataset = VOCDetection(args.training_dataset, preproc_s3fd(img_dim, rgb_means, cfg['max_expand_ratio']), AnnotationTransform())

    epoch_size = math.ceil(len(dataset) / args.batch_size)
    max_iter = args.max_epoch * epoch_size

    stepvalues = (200 * epoch_size, 250 * epoch_size)
    step_index = 0

    if args.resume_epoch > 0:
        start_iter = args.resume_epoch * epoch_size
    else:
        start_iter = 0

    for iteration in range(start_iter, max_iter):
        if iteration % epoch_size == 0:
            # create batch iterator
            batch_iterator = iter(data.DataLoader(dataset, batch_size, shuffle=True, num_workers=args.num_workers, collate_fn=detection_collate, pin_memory=True))
            # if (epoch % 10 == 0 and epoch > 0) or (epoch % 5 == 0 and epoch > 200):
            if (epoch % 2 == 0 and epoch > 0) or (epoch % 1 == 0 and epoch > 10): #kind of lower standards
                torch.save(net.state_dict(), args.save_folder + 'S3FD_{}_epoch_'.format(args.net) + repr(epoch) + '.pth')
            epoch += 1

        load_t0 = time.time()
        if iteration in stepvalues:
            step_index += 1
        lr = adjust_learning_rate(optimizer, args.gamma, epoch, step_index, iteration, epoch_size)

        # load train data
        images, targets = next(batch_iterator)
        if args.cuda:
            images = Variable(images.cuda())
            targets = [Variable(anno.cuda()) for anno in targets]
        else:
            images = Variable(images)
            targets = [Variable(anno) for anno in targets]

        # forward
        out = net(images)
        
        # backprop
        optimizer.zero_grad()
        loss_l, loss_c = criterion(out, priors, targets)
        loss = loss_l + cfg['conf_weight'] * loss_c
        loss.backward()
        optimizer.step()
        load_t1 = time.time()
        print('Epoch:' + repr(epoch) + ' || epochiter: ' + repr(iteration % epoch_size) + '/' + repr(epoch_size) +
              '|| Totel iter ' + repr(iteration) + ' || L: %.4f C: %.4f||' % (loss_l.item(), cfg['conf_weight'] * loss_c.item()) +
              'Batch time: %.4f sec. ||' % (load_t1 - load_t0) + 'LR: %.8f' % (lr))
        if writer is not None:
            writer.add_scalar('train/loss_l', loss_l.item(), iteration)
            writer.add_scalar('train/loss_c', cfg['conf_weight'] * loss_c.item(), iteration)
            writer.add_scalar('train/lr', lr, iteration)

    torch.save(net.state_dict(), args.save_folder + 'Final_{}_S3FD.pth'.format(args.net))


def adjust_learning_rate(optimizer, gamma, epoch, step_index, iteration, epoch_size):
    """Sets the learning rate 
    # Adapted from PyTorch Imagenet example:
    # https://github.com/pytorch/examples/blob/master/imagenet/main.py
    """
    if epoch < 0:
        lr = 1e-6 + (args.lr-1e-6) * iteration / (epoch_size * 5) 
    else:
        lr = args.lr * (gamma ** (step_index))
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr
    return lr
    
if __name__ == '__main__':
    train()
