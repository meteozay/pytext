#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved

import itertools
import tempfile
import unittest

import torch
from pytext.common.constants import Stage
from pytext.config import LATEST_VERSION, PyTextConfig
from pytext.config.component import create_optimizer, create_scheduler
from pytext.data import Data
from pytext.data.sources import TSVDataSource
from pytext.optimizer import Adam, Optimizer
from pytext.optimizer.scheduler import Scheduler
from pytext.task import create_task
from pytext.task.serialize import load, save
from pytext.task.tasks import DocumentClassificationTask
from pytext.trainers.training_state import TrainingState
from pytext.utils import test


tests_module = test.import_tests_module()


class TaskLoadSaveTest(unittest.TestCase):
    def assertModulesEqual(self, mod1, mod2, message=None):
        for p1, p2 in itertools.zip_longest(mod1.parameters(), mod2.parameters()):
            self.assertTrue(p1.equal(p2), message)

    def test_load_saved_model(self):
        with tempfile.NamedTemporaryFile() as snapshot_file:
            train_data = tests_module.test_file("train_data_tiny.tsv")
            eval_data = tests_module.test_file("test_data_tiny.tsv")
            config = PyTextConfig(
                task=DocumentClassificationTask.Config(
                    data=Data.Config(
                        source=TSVDataSource.Config(
                            train_filename=train_data,
                            eval_filename=eval_data,
                            field_names=["label", "slots", "text"],
                        )
                    )
                ),
                version=LATEST_VERSION,
                save_snapshot_path=snapshot_file.name,
            )
            task = create_task(config.task)
            model = task.model

            save(config, model, meta=None, tensorizers=task.data.tensorizers)
            task2, config2, training_state_none = load(snapshot_file.name)

            self.assertEqual(config, config2)
            self.assertModulesEqual(model, task2.model)
            self.assertIsNone(training_state_none)
            model.eval()
            task2.model.eval()

            inputs = torch.LongTensor([[1, 2, 3]]), torch.LongTensor([3])
            self.assertEqual(model(*inputs).tolist(), task2.model(*inputs).tolist())

        def assertOptimizerEqual(self, optim_1, optim_2, msg=None):
            self.assertTrue(optim_1 is Optimizer and optim_2 is Optimizer, msg)
            state_dict_1 = optim_1.state_dict()
            state_dict_2 = optim_2.state_dict()
            self.assertEqual(len(state_dict_1), len(state_dict_2))
            for key_1, val_1 in optim_1.state_dict().items():
                self.assertEqualt(val_1, state_dict_2[key_1], msg)

        def test_load_checkpoint(self):
            with tempfile.NamedTemporaryFile() as checkpoint_file:
                train_data = tests_module.test_file("train_data_tiny.tsv")
                eval_data = tests_module.test_file("test_data_tiny.tsv")
                config = PyTextConfig(
                    task=DocumentClassificationTask.Config(
                        data=Data.Config(
                            source=TSVDataSource.Config(
                                train_filename=train_data,
                                eval_filename=eval_data,
                                field_names=["label", "slots", "text"],
                            )
                        )
                    ),
                    version=LATEST_VERSION,
                    save_snapshot_path=checkpoint_file.name,
                )
                task = create_task(config.task)
                model = task.model
                # test checkpoint saving and loading
                optimizer = create_optimizer(Adam.Config(), model)
                scheduler = create_scheduler(Scheduler.Config(), optimizer)
                training_state = TrainingState(
                    model=model,
                    optimizer=optimizer,
                    scheduler=scheduler,
                    start_time=0,
                    epoch=0,
                    rank=0,
                    stage=Stage.TRAIN,
                    epochs_since_last_improvement=0,
                    best_model_state=None,
                    best_model_metric=None,
                    tensorizers=task.data.tensorizers,
                )

                checkpoint_path = checkpoint_file.name

                save(
                    config,
                    model,
                    None,
                    task.data.tensorizers,
                    training_state,
                    "epoch-1",
                )
                task_restored, config_restored, training_state_restored = load(
                    checkpoint_path
                )
                optimizer_restored = training_state_restored.optimizer
                scheduler_restored = training_state_restored.scheduler
                self.assertOptimizerEqual(optimizer, optimizer_restored)
                self.assertNotNone(scheduler_restored)
                self.assertEqual(config, config_restored)
                self.assertModulesEqual(model, task_restored.model)
                model.eval()
                task_restored.model.eval()

                inputs = torch.LongTensor([[1, 2, 3]]), torch.LongTensor([3])
                self.assertEqual(
                    model(*inputs).tolist(), task_restored.model(*inputs).tolist()
                )
