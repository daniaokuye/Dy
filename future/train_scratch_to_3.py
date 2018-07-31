'''
almost same as train.py;
but it is setting for new covolution layer with little kernel
in a different way
'''

import sys,os

sys.path.append('.')
print os.getcwd()
from mxnet import gluon, autograd
import mxnet as mx
from layers.sphere_net import AngleLoss, test_accur, SphereNet20
from layers.data import train_valid_test_loader
# from layers.dy_conv import origin_conv, new_conv, constrain_kernal_num
from layers.params import global_param, gls  # , alpha, compressed_root  #
from units import getParmas, init_sphere
import os, pickle
from scratch_net import new_location_conv


def train_compressed_model(gpu=None, compressed_root='log_4dy_Ns3/transfed', lr=0.0001):
    my_fun = new_location_conv
    # save_global_prams = True
    loaded_model = compressed_root + "/spherenet_ft_Ns.model"
    loaded_param = compressed_root + "/global.param"
    ctx = mx.gpu(gpu)
    # several paramers need update for different duty |
    # and notice params need to be updated

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    data_fold = "/home1/CASIA-WebFace/aligned_Webface-112X96/"
    batch_size = 192
    mnet = SphereNet20(my_fun=my_fun, use_bn=True)
    stop_epoch = 300

    # initia the net and return paramers of bn -- gamma
    _ = init_sphere(mnet, loaded_model, ctx)
    # data iteratier
    train_data_loader, valid_data_loader \
        = train_valid_test_loader(data_fold, batch_size=batch_size)
    mnet.feature = False  # get features or classes throught spherenet
    # if not mnet.has_mask:
    #     mnet.build_mask(mask_path=loaded_param)
    Aloss = AngleLoss()
    # L1_loss = gluon.loss.L1Loss()
    # finetune the net
    params = getParmas(mnet, mode='conv')
    trainer = gluon.Trainer(params, 'adam', {'learning_rate': lr})

    # initia the mask for prune
    # mask_type = 'conv'  # 'conv'or 'bn'
    # so try not set these two file in one file
    # if os.path.exists(loaded_param):
    #     with open(loaded_param)as f:
    #         sv = pickle.load(f)
    #     global_param.load_param(sv, ctx=ctx)
    # else:
    #     global_param.set_param(params.keys(), ctx=ctx)

    epoch_train = len(train_data_loader)
    # train
    for epoch in range(stop_epoch):
        j = epoch * epoch_train
        for i, (batch, label) in enumerate(train_data_loader):
            batch = batch.as_in_context(ctx)
            label = label.as_in_context(ctx)
            # global_param.iter = i + j
            with autograd.record():
                out = mnet(batch)
                loss = Aloss(out[0], out[1], label)
                # loss_nums = constrain_kernal_num(mnet)
                # loss = loss_a + loss_nums * alpha
            loss.backward()
            trainer.step(batch_size)
            mx.nd.waitall()

            # value2 = loss_nums.asscalar()
            value = loss.asscalar() / batch_size  # + value2
            sw.add_scalar(tag='Loss', value=value, global_step=i + j)
            # sw.add_scalar(tag='Loss_inKernel', value=value2, global_step=i + j)
            if i % 200 == 0:
                print('iter:%d,loss:%4.3f' % (i + j, value))
            # if isinstance(my_fun(1, 1), new_conv):
            #     # get sparse of the dynamic
            #     s_dict = get_sparse_ratio()
            #     for k, v in s_dict:
            #         sw.add_scalar(tag=k, value=v, global_step=j)

        # validation
        for i, (batch, label) in enumerate(valid_data_loader):
            batch = batch.as_in_context(ctx)
            label = label.as_in_context(ctx)
            out = mnet(batch)
            discroc, controc = test_accur(label, i + j, *out)
            sw.add_scalar(tag='RocDisc', value=discroc.asscalar(), global_step=i + j)
            sw.add_scalar(tag='RocCont', value=controc.asscalar(), global_step=i + j)
        # save model
        mnet.save_params(loaded_model)
        # save the params of mask
        with open(loaded_param, 'w')as f:
            pickle.dump(global_param, f)


if __name__ == "__main__":
    import argparse

    parse = argparse.ArgumentParser(description='paramers for compressed model trainning')
    parse.add_argument('--gpu', type=int, default=0)
    parse.add_argument('--root', type=str, default='../log/future')
    parse.add_argument('--lr', type=float, default=0.0001)
    args = parse.parse_args()
    global sw
    sw = gls.set_sw(args.root)
    train_compressed_model(gpu=args.gpu, compressed_root=args.root, lr=args.lr)
