from sphere_net import SphereNet20, AngleLoss, test_accur
from mxnet import gluon, autograd
import mxnet as mx
import data, pickle, os

from layers.dy_conv import origin_conv, new_conv
from layers.params import global_param, sw
from units import getParmas, init_sphere


def train_model():
    my_fun = origin_conv
    mnet = SphereNet20(my_fun=my_fun)
    ctx = mx.gpu(3)
    lr = 0.000001
    batch_size = 192
    stop_epoch = 300
    loaded_model = "log_bn_dy/spherenet_bn_4dy.model"
    loaded_param = "log_bn_dy/global.param"
    data_fold = "/home1/CASIA-WebFace/aligned_Webface-112X96/"

    save_global_prams = True
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
        global_param.load_param(sv, ctx=ctx)
    else:
        global_param.set_param(params.keys(), ctx=ctx)

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
                loss = Aloss(out[0], out[1], label)
                # loss_bn = reduce(lambda x, y: x + y, [L1_loss(v) for k, v in gammas])
                # loss = loss_a + loss_bn
            loss.backward()
            trainer.step(batch_size)
            value = loss.asscalar() / batch_size
            sw.add_scalar(tag='Loss', value=value, global_step=i + j)
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
        if save_global_prams:  # isinstance(my_fun(1, 1), new_conv):
            # save the params of mask
            with open(loaded_param, 'w')as f:
                pickle.dump(global_param, f)


if __name__ == "__main__":
    train_model()
    print('o')
