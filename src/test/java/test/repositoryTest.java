package test;

import com.alibaba.fastjson.JSONObject;
import com.alibaba.fastjson.serializer.SerializerFeature;
import lombok.extern.slf4j.Slf4j;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.junit4.SpringJUnit4ClassRunner;
import test.domain.PO.ACTED_IN;
import test.domain.PO.DynamicRelationShip;
import test.domain.PO.Movie;
import test.domain.PO.Person;
import test.repository.ACTED_INRepository;
import test.repository.DynamicRelationShipRepository;
import test.repository.NodeRepository;

import javax.annotation.Resource;
import java.util.List;

@Slf4j
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@RunWith(SpringJUnit4ClassRunner.class)
public class repositoryTest {

    @Resource
    NodeRepository nodeRepository;
    @Resource
    ACTED_INRepository acted_inRepository;
    @Resource
    DynamicRelationShipRepository dynamicRelationShipRepository;

    @Test
    public void testSelectAll(){
        List<Person> nodes = nodeRepository.selectAll();
        log.info("result:{}", JSONObject.toJSONString(nodes, SerializerFeature.PrettyFormat));
    }

    @Test
    public void testFindByName(){
        Person person = nodeRepository.findByName("Keanu Reeves");
        log.info("testFindByName:{}", JSONObject.toJSONString(person, SerializerFeature.PrettyFormat));
    }

    @Test
    public void testActed_In(){
        List<ACTED_IN> actedIns = acted_inRepository.findByNames("Helen Hunt", "As Good as It Gets");
        log.info("testActed_In:{}", JSONObject.toJSONString(actedIns, SerializerFeature.PrettyFormat));
    }

    @Test
    public void testDynamicRelationShip(){
        List<DynamicRelationShip<Person, Movie>> dynamicRelationShip = dynamicRelationShipRepository.findByNames("Helen Hunt", "Cloud Atlas");
        log.info("testDynamicRelationShip:{}", JSONObject.toJSONString(dynamicRelationShip, SerializerFeature.PrettyFormat));
    }

}
