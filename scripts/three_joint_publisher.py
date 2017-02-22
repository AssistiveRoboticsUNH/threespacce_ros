#!/usr/bin/env python
import roslib
import rospy
import tf
import tf2_ros
import geometry_msgs.msg
import serial
import time
import math
import string
import glob
import sensor_table
import find_dng
import threespace as tsa
from threespace import *
from ThreeJoint import ThreeJoint
from socket import *
from threespace_ros.msg import dataVec


def quaternion_to_msg(q):
    msg = Quaternion()
    msg.x = q[0]
    msg.y = q[1]
    msg.z = q[2]
    msg.w = q[3]
    return msg


class SinglePublisher:
    def __init__(self):
        rospy.init_node("publisher")
        r = rospy.Rate(100)
        suffix = "_data_vec"
        dongle_list = find_dng.returnDev("dng")
        publishers = {}
        dv_publishers = {}
        broadcasters = {}
        joints = {}
        upper_topic = rospy.get_param('upper', 'none')
        rospy.logerr(upper_topic)
        if upper_topic == 'none':
            rospy.logerr('No topic for upper joint found, exiting')
        else:
            joints[upper_topic] = ThreeJoint('upper', upper_topic, 'world', 0.30)
            lower_topic = rospy.get_param('lower', 'none')
            rospy.logerr(lower_topic)
            if lower_topic == 'none':
                rospy.logerr('No topic for lower joint found')
            else:
                joints[lower_topic] = ThreeJoint('lower', upper_topic, joints.get(upper_topic).name + '3', 0.30)
                hand_topic = rospy.get_param('hand', 'none')
                rospy.logerr(hand_topic)
                if hand_topic == 'none':
                    rospy.logerr('No topic for hand joint found')
                else:
                    joints[hand_topic] = ThreeJoint('hand', lower_topic, joints.get(lower_topic).name + '3', 0.05)

        if len(dongle_list) == 0:
            rospy.logerr("No dongles found, exiting")
            exit()
        for d in dongle_list:
            tsa.TSDongle.broadcastSynchronizationPulse(d)
            for device in d:
                if device is None:
                    rospy.logerr("No Sensor Found")
                else:
                    id_ = str(device)
                    id_ = id_[id_.find('W'):-1]
                    rospy.logerr(id_)
                    frame = sensor_table.sensor_table.get(id_)
                    rospy.logwarn("Adding publisher for %s : %s", id_, frame)
                    rospy.logwarn("Battery at %s Percent ", tsa.TSWLSensor.getBatteryPercentRemaining(device))
                    br = tf2_ros.TransformBroadcaster()
                    dv_pub = rospy.Publisher(frame + suffix, dataVec, queue_size=100)
                    broadcasters[frame] = br
                    dv_publishers[frame] = dv_pub
                    tsa.TSWLSensor.setStreamingSlots(device, slot0='getTaredOrientationAsQuaternion',
                                                     slot1='getAllCorrectedComponentSensorData')

        t = geometry_msgs.msg.TransformStamped()
        t2 = geometry_msgs.msg.TransformStamped()
        t3 = geometry_msgs.msg.TransformStamped()
        dv = dataVec()
        dev_list = []
        for d in dongle_list:
            for dev in d:
                if dev is not None:
                    dev_list.append(dev)

        while not rospy.is_shutdown():
            for device in dev_list:
                if device is not None:
                    batch = tsa.TSWLSensor.getStreamingBatch(device)
                    if batch is not None:
                        # print(batch)
                        frame = sensor_table.sensor_table.get(id_)
                        quat = batch[0:4]
                        full = batch[4:]
                        id_ = str(device)
                        id_ = id_[id_.find('W'):-1]
                        dp = dv_publishers.get(frame)
                        dv.header.stamp = rospy.get_rostime()
                        dv.quat.quaternion.x = -quat[2]
                        dv.quat.quaternion.y = quat[0]
                        dv.quat.quaternion.z = -quat[1]
                        dv.quat.quaternion.w = quat[3]
                        t.transform.rotation = dv.quat.quaternion
                        dv.gyroX = full[0]
                        dv.gyroY = full[1]
                        dv.gyroZ = full[2]
                        dv.accX = full[3]
                        dv.accY = full[4]
                        dv.accZ = full[5]
                        dv.comX = full[6]
                        dv.comY = full[7]
                        dv.comZ = full[8]

                        t.header.stamp = rospy.Time.now()
                        t2.header.stamp = rospy.Time.now()
                        t3.header.stamp = rospy.Time.now()

                        t.header.frame_id = joints.get(frame).parent
                        t2.header.frame_id = joints.get(frame).parent
                        t3.header.frame_id = joints.get(frame).parent

                        t.child_frame_id = joints.get(frame).name
                        t2.child_frame_id = joints.get(frame).name + '2'
                        t3.child_frame_id = joints.get(frame).name + '3'

                        (roll, pitch, yaw) = tf.transformations.euler_from_quaternion(
                            [t.transform.rotation.x,
                             t.transform.rotation.y,
                             t.transform.rotation.z,
                             t.transform.rotation.w])
                        if yaw == 0.0 or pitch == 0.0 or roll == 0.0:
                            continue
                        if joints.get(frame).set is False:
                            joints.get(frame).initYaw = yaw
                            joints.get(frame).intPitch = pitch
                            joints.get(frame).initRoll = roll
                            rospy.logerr(
                                [joints.get(frame).initYaw, joints.get(frame).initPitch, joints.get(frame).initRoll])
                            joints.get(frame).set = True

                        if abs(joints.get(frame).roll - roll - joints.get(frame).initRoll) > 0.01:
                            joints.get(frame).roll = roll - joints.get(frame).initRoll
                        if abs(joints.get(frame).pitch - pitch - joints.get(frame).initPitch) > 0.01:
                            joints.get(frame).pitch = pitch - joints.get(frame).initPitch
                            rospy.logerr([yaw, pitch, roll])
                            rospy.logerr([joints.get(frame).yaw, joints.get(frame).pitch, joints.get(frame).roll])
                            rospy.logerr([joints.get(frame).x, joints.get(frame).y, joints.get(frame).z])
                            rospy.logerr("*******************************")
                        if abs(joints.get(frame).yaw - yaw - joints.get(frame).initYaw) > 0.01:
                            joints.get(frame).yaw = yaw - joints.get(frame).initYaw

                        # q = tf.transformations.quaternion_from_euler(roll, pitch, yaw)
                        q = tf.transformations.quaternion_from_euler(joints.get(
                            frame).roll, joints.get(frame).pitch, joints.get(frame).yaw)
                        msg = geometry_msgs.msg.Quaternion(q[0], q[1], q[2], q[3])

                        t.transform.rotation = msg
                        t2.transform.rotation = t.transform.rotation
                        t3.transform.rotation = t.transform.rotation

                        # joints.get(frame).x = joints.get(frame).radius * math.sin(joints.get(frame).pitch) * math.sin(
                        #     joints.get(frame).yaw)
                        # joints.get(frame).y = joints.get(frame).radius * math.cos(joints.get(frame).pitch) * math.sin(
                        #     joints.get(frame).yaw)
                        # joints.get(frame).z = joints.get(frame).radius * math.cos(joints.get(frame).pitch)

                        joints.get(frame).x = joints.get(frame).radius * math.cos(joints.get(frame).pitch)

                        joints.get(frame).y = joints.get(frame).radius * math.sin(joints.get(frame).pitch) * math.cos(
                             joints.get(frame).yaw)

                        joints.get(frame).z = joints.get(frame).radius * math.cos(joints.get(frame).pitch)

                        t.transform.translation.x = joints.get(frame).x * 2
                        t.transform.translation.y = joints.get(frame).y
                        t.transform.translation.z = 0
                        t2.transform.translation.x = joints.get(frame).x
                        t2.transform.translation.y = joints.get(frame).y
                        t2.transform.translation.z = 0
                        t3.transform.translation.x = joints.get(frame).x * 3
                        t3.transform.translation.y = 0
                        t3.transform.translation.z = 0

                        # t.transform.translation.x = joints.get(frame).radius * math.sin(
                        #     joints.get(frame).pitch) * math.cos(joints.get(frame).yaw)
                        # t.transform.translation.y = joints.get(frame).radius * math.sin(
                        #     joints.get(frame).pitch) * math.sin(joints.get(frame).yaw)
                        # t.transform.translation.z = joints.get(frame).radius * math.cos(joints.get(frame).yaw)
                        # t2.transform.translation.x = joints.get(frame).radius * 2 * math.sin(
                        #     joints.get(frame).pitch) * math.cos(joints.get(frame).yaw)
                        # t2.transform.translation.y = joints.get(frame).radius * 2 * math.sin(
                        #     joints.get(frame).pitch) * math.sin(joints.get(frame).yaw)
                        # t2.transform.translation.z = joints.get(frame).radius * 2 * math.cos(joints.get(frame).yaw)

                        br = tf2_ros.TransformBroadcaster()
                        # br2 = tf2_ros.TransformBroadcaster()
                        #  br3 = tf2_ros.TransformBroadcaster()

                        br.sendTransform(t)
                        # br2.sendTransform(t2)
                        # br3.sendTransform(t3)
                        dp.publish(dv)
                    else:
                        # rospy.logerr("None")
                        pass
        for d in dongle_list:
            tsa.TSDongle.close(d)
        print publishers
        print dv_publishers
        print broadcasters
        exit()


if __name__ == "__main__":
    SinglePublisher()
