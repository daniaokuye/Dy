from layers.sphere_net import SphereNet20, AngleLoss, test_accur
from mxnet import gluon, autograd
import mxnet as mx
import os, pickle
from layers import data

from layers.dy_conv import origin_conv, new_conv, constrain_kernal_num, constrain_gamma
from layers.params import global_param, alpha, beta, gls
from units import getParmas, init_sphere


def train_model(gpu=None, root='', lr=0.0001, data_fold=None, batch_size=None, use_bn=True):
    my_fun = new_conv
    save_global_prams = True
    loaded_model = root + "/spherenet.model"
    loaded_param = root + "/global.param"
    ctx = mx.gpu(gpu)
    # several paramers need update for different duty |
    # and notice params need to be updated

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # data_fold = "/home1/CASIA-WebFace/aligned_Webface-112X96/"
    # batch_size = 192
    mnet = SphereNet20(my_fun=my_fun, use_bn=use_bn)
    # lr = lr
    stop_epoch = 300

    # initia the net and return paramers of bn -- gamma
    gammas = init_sphere(mnet, loaded_model, ctx)
    # data iteratier
    train_data_loader, valid_data_loader \
        = data.train_valid_test_loader(data_fold, batch_size=batch_size)
    mnet.feature = False  # get features or classes throught spherenet

    Aloss = AngleLoss()
    # L1_loss = gluon.loss.L1Loss()
    # finetune the net
    params = getParmas(mnet, mode='conv')
    trainer = gluon.Trainer(params, 'adam', {'learning_rate': lr})

    # initia the mask for prune
    # mask_type = 'conv'  # 'conv'or 'bn'
    # so try not set these two file in one file
    if os.path.exists(loaded_param):
        with open(loaded_param)as f:
            sv = pickle.load(f)
        global_param.load_param(sv)
    else:
        if isinstance(my_fun(1, 1), new_conv):
            global_param.set_param(params.keys(), ctx=ctx)
        elif isinstance(my_fun(1, 1), origin_conv):
            global_param.set_param(gammas.keys(), ctx=ctx)

    epoch_train = len(train_data_loader)
    # train
    for epoch in range(stop_epoch):
        j = epoch * epoch_train
        for i, (batch, label) in enumerate(train_data_loader):
            batch = batch.as_in_context(ctx)
            label = label.as_in_context(ctx)
            global_param.iter = i + j
            with autograd.record():
                out = mnet(batch)
                loss_a = Aloss(out[0], out[1], label)
                loss_nums = constrain_kernal_num(mnet.collect_params(), ctx=ctx) * alpha
                if use_bn:
                    loss_bn = constrain_gamma(mnet, i + j, ctx) * beta
                    loss_nums = loss_nums + loss_bn
                loss = loss_a + loss_nums
            loss.backward()
            trainer.step(batch_size)
            value2 = loss_nums.asscalar()
            value = loss_a.asscalar() / batch_size + value2
            sw.add_scalar(tag='Loss', value=value, global_step=i + j)
            sw.add_scalar(tag='Loss_inKernel', value=value2, global_step=i + j)
            if i % 200 == 0:
                print('iter:%d,loss:%4.5f' % (i + j, value))
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
        mnet.save_parameters(loaded_model)
        if save_global_prams:  # isinstance(my_fun(1, 1), new_conv):
            # save the params of mask
            global_param.save_param(loaded_param)


if __name__ == "__main__":
    import argparse

    parse = argparse.ArgumentParser(description='paramers for compressed model trainning')
    parse.add_argument('--gpu', type=int, default=0,
                       help='default=0')
    parse.add_argument('--root', type=str, default='log/5log_bn_dy',
                       help='notice there has no "/" after it')
    parse.add_argument('--lr', type=float, default=0.0001)
    parse.add_argument('--stopat', type=float, default=0.0,
                       help='force using constrain to top k when probablity reduce to this point')
    parse.add_argument('--use_bn', type=bool, default=False,
                       help="whether use BN or not")
    parse.add_argument('--use_group_constrain', type=bool, default=False,
                       help="used for selcet group constrain or not in constrain_kernal_num")
    parse.add_argument('--data_fold', type=str, default="/home1/CASIA-WebFace/aligned_Webface-112X96/")
    parse.add_argument('--batch_size', type=int, default=192)
    parse.add_argument('--thres_constrain', type=int, default=20000,
                       help='when to use constrain top k')
    parse.add_argument('--thres_constrain_BN', type=int, default=100000,
                       help='when to constrain Batch Normal')
    args = parse.parse_args()
    global sw
    sw = gls.set_sw(args.root)

    global_param.threshold_stop_mask = args.stopat
    global_param.set_thr(args.thres_constrain)
    global_param.set_thr_bn(args.thres_constrain_BN)

    train_model(gpu=args.gpu, root=args.root, lr=args.lr,
                data_fold=args.data_fold,
                batch_size=args.batch_size, use_bn=args.use_bn)
    print('o')
